# -*- coding: utf-8 -*-
"""
抖音账号扫码登录向导脚本 (弹窗模式)
功能：一键拉起可视化 Chrome 浏览器窗口，打开抖音官网并自动唤起登录二维码，
     智能捕获登录完成状态，自动落盘持久化凭证，安全退出。
"""
import asyncio
import os
import sys
import json
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LoginBrowser")

SESSION_DIR = os.path.abspath("./douyin_session")
STORAGE_STATE_PATH = os.path.join(SESSION_DIR, "storage_state.json")

def clean_locks():
    """清理残留的进程锁文件"""
    lock_file = os.path.join(SESSION_DIR, "lockfile")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except Exception:
            pass

def is_logged_in() -> bool:
    """检查本地是否已存在有效的抖音登录凭证"""
    if not os.path.exists(STORAGE_STATE_PATH):
        return False
    try:
        with open(STORAGE_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cookies = data.get("cookies", [])
        names = [c["name"] for c in cookies]
        auth_keys = ["sessionid", "sessionid_ss", "sid_guard", "passport_auth_status", "uid_tt"]
        return any(k in names for k in auth_keys)
    except Exception:
        return False

async def main(clear_old: bool = False):
    clean_locks()

    if clear_old:
        import shutil
        print("[*] 正在清除旧登录会话与缓存...")
        if os.path.exists(STORAGE_STATE_PATH):
            try:
                os.remove(STORAGE_STATE_PATH)
            except Exception:
                pass
        if os.path.exists(SESSION_DIR):
            try:
                shutil.rmtree(SESSION_DIR, ignore_errors=True)
            except Exception:
                pass

    os.makedirs(SESSION_DIR, exist_ok=True)
    clean_locks()

    print("\n" + "=" * 72)
    print("        🚀 抖音账号可视化弹窗登录向导 (Douyin Login Helper)")
    print("=" * 72)
    print("【操作指引】：")
    print(" 1. 程序即将为你拉起 Chrome 浏览器并访问抖音官网 (douyin.com)。")
    print(" 2. 页面就绪后，将自动为你点击右上角【登录】按钮，居中调出大号二维码。")
    print(" 3. 请打开手机【抖音 App】-> 首页右上角【扫一扫】，扫描屏幕中的二维码。")
    print(" 4. 在手机上点击【确认登录】，程序将自动捕获凭证并秒级保存退出！")
    print("=" * 72 + "\n")

    async with async_playwright() as p:
        print("[1/4] 正在拉起 Chrome 浏览器窗口...")
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=False,
                viewport={"width": 1280, "height": 820},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars"
                ]
            )
        except Exception as e:
            print(f"[!] 启动浏览器失败: {e}")
            print("👉 提示：如果提示浏览器已被占用，请先关闭其他可能正在运行的 Chrome 或 Python 脚本。")
            return False

        page = context.pages[0] if context.pages else await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        print("[2/4] 正在打开抖音官网 (https://www.douyin.com/)...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            print(f"[*] 页面加载提示: {e} (继续执行)")

        await asyncio.sleep(2.5)

        # 尝试自动点击右上角【登录】按钮，主动唤起居中大号二维码
        try:
            login_btn = page.locator('header button:has-text("登录"), button:has-text("登录")').first
            if await login_btn.is_visible():
                print("[*] 正在自动点击页面右上角【登录】按钮调出二维码...")
                await login_btn.click()
                await asyncio.sleep(1.5)
        except Exception as e:
            logger.debug(f"唤起登录框提示: {e}")

        print("\n" + "-" * 72)
        print(">>> 📱 请使用手机【抖音 App】扫描屏幕上的二维码，并在手机上点击【确认登录】 <<<")
        print(">>> (若你手动关闭了浏览器窗口，程序也会安全捕获并退出，无需担心崩溃) <<<")
        print("-" * 72 + "\n")

        login_success = False
        nickname_detected = ""

        # 最长轮询等待 3 分钟 (180 次，每次 1 秒)
        for second in range(180):
            await asyncio.sleep(1.0)

            # 检查浏览器是否已被手动关闭
            if page.is_closed() or not context.pages:
                print("[*] 浏览器窗口已关闭，正在核验登录结果...")
                break

            try:
                # 检查 Cookie 中的关键身份令牌
                cookies = await context.cookies()
                names = [c["name"] for c in cookies]
                auth_found = [k for k in ["sessionid", "sessionid_ss", "sid_guard", "passport_auth_status", "uid_tt"] if k in names]

                # 检查页面右上角是否已显示已登录头像或用户信息
                has_avatar = await page.locator('header img[class*="avatar"], [data-e2e="user-info"], div:has-text("我的") img').count()
                login_btn_count = await page.locator('header button:has-text("登录")').count()

                if auth_found or (has_avatar > 0 and login_btn_count == 0):
                    print(f"\n[+] 🎯 成功捕获到账号登录认证信息！(令牌字段: {auth_found})")
                    login_success = True

                    # 尝试读取并打印已登录账号的昵称
                    try:
                        name_el = page.locator('[data-e2e="user-info"] span, header span[class*="name"]').first
                        if await name_el.is_visible():
                            nickname_detected = await name_el.inner_text()
                    except Exception:
                        pass
                    break
            except Exception:
                pass

        print("\n[3/4] 正在持久化保存登录凭证到本地...")
        try:
            await context.storage_state(path=STORAGE_STATE_PATH)
            await asyncio.sleep(1)
            await context.close()
        except Exception as e:
            logger.debug(f"保存会话上下文异常: {e}")

    # [4/4] 最终校验与报告
    print("[4/4] 正在核验本地持久化状态...")
    valid = is_logged_in()
    print("=" * 72)
    if valid:
        print("🎉 恭喜！抖音登录凭证已完整保存并验证成功！")
        if nickname_detected:
            print(f"👤 当前登录抖音账号: 【{nickname_detected}】")
        print(f"📁 凭证目录: {SESSION_DIR}")
        print(f"📄 存储状态: {STORAGE_STATE_PATH}")
        print("\n✅ 现在你可以启动自动回复服务 (双击 start_windows.bat 或执行 python server.py)！")
    else:
        print("❌ 未检测到有效登录凭据。")
        print("👉 可能原因：手机端尚未点击确认登录，或在扫码前提前退出了窗口。")
        print("👉 解决办法：请重新运行 python login_browser.py 扫码。")
    print("=" * 72 + "\n")
    return valid

if __name__ == "__main__":
    clear = any(arg in sys.argv for arg in ["--switch", "--clear", "-s", "-c"])
    asyncio.run(main(clear_old=clear))
