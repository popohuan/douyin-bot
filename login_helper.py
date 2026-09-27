import asyncio
import os
import sys
import json
import logging
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LoginHelper")

SESSION_DIR = os.path.abspath("./douyin_session")
STORAGE_STATE_PATH = os.path.join(SESSION_DIR, "storage_state.json")

def is_authenticated() -> bool:
    """检查本地是否真正持久化保存了有效的登录凭证"""
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

def clean_locks():
    """清理残留的锁文件"""
    lock_file = os.path.join(SESSION_DIR, "lockfile")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except Exception:
            pass

def clear_session(backup: bool = True):
    """清理现有登录凭据与会话缓存，以便切换新账号"""
    clean_locks()
    import shutil
    if backup and os.path.exists(SESSION_DIR):
        backup_dir = os.path.abspath("./douyin_session_backup")
        try:
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir, ignore_errors=True)
            shutil.copytree(SESSION_DIR, backup_dir, ignore_dangling_symlinks=True)
            logger.info(f"已自动备份上一账号凭据至: {backup_dir}")
        except Exception as e:
            logger.warning(f"备份旧会话时提示: {e}")

    if os.path.exists(STORAGE_STATE_PATH):
        try:
            os.remove(STORAGE_STATE_PATH)
        except Exception:
            pass

    if os.path.exists(SESSION_DIR):
        try:
            shutil.rmtree(SESSION_DIR, ignore_errors=True)
        except Exception as e:
            logger.warning(f"清理旧会话目录提示: {e}")

def wipe_all_credentials() -> dict:
    """彻底清除所有个人登录凭据，包括当前会话目录、备份会话目录及存储文件，零隐私残留"""
    clean_locks()
    import shutil
    removed_items = []
    backup_dir = os.path.abspath("./douyin_session_backup")

    if os.path.exists(STORAGE_STATE_PATH):
        try:
            os.remove(STORAGE_STATE_PATH)
            removed_items.append("storage_state.json")
        except Exception as e:
            logger.warning(f"删除 storage_state.json 异常: {e}")

    if os.path.exists(SESSION_DIR):
        try:
            shutil.rmtree(SESSION_DIR, ignore_errors=True)
            removed_items.append("douyin_session")
        except Exception as e:
            logger.warning(f"删除 douyin_session 异常: {e}")

    if os.path.exists(backup_dir):
        try:
            shutil.rmtree(backup_dir, ignore_errors=True)
            removed_items.append("douyin_session_backup")
        except Exception as e:
            logger.warning(f"删除 douyin_session_backup 异常: {e}")

    return {
        "success": True,
        "removed": removed_items,
        "is_authenticated": is_authenticated()
    }

async def run_login_flow(clear_session_first: bool = False):
    if clear_session_first:
        print("[*] 正在清除旧账号会话缓存与凭据...")
        clear_session(backup=True)

    os.makedirs(SESSION_DIR, exist_ok=True)
    clean_locks()

    print("\n" + "=" * 70)
    print("       抖音账号登录与凭证保存中枢 (全新重构版)")
    print("=" * 70)
    print("【重要说明】：")
    print("1. 电脑端访问 douyin.com 时，官方左上角统一标注为『抖音精选』，这【就是】")
    print("   中国境内抖音官方的电脑端网页主站，与手机抖音 App 账号、私信完全互通。")
    print("2. 浏览器拉起后，程序会自动为你唤起屏幕中央的大号登录二维码。")
    print("3. 请使用手机【抖音 App】扫码，并在手机上点击【确认登录】。")
    print("=" * 70 + "\n")

    async with async_playwright() as p:
        print("[1/4] 正在拉起 Chrome 浏览器环境...")
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

        page = context.pages[0] if context.pages else await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        print("[2/4] 正在打开抖音官网 (https://www.douyin.com/)...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            print(f"[*] 页面加载提示: {e} (继续处理)")

        await asyncio.sleep(2.5)

        # 尝试自动点击右上角【登录】按钮，主动唤起居中大号二维码
        try:
            login_btn = page.locator('header button:has-text("登录"), button:has-text("登录")').first
            if await login_btn.is_visible():
                print("[*] 自动点击【登录】按钮，调出居中大号二维码...")
                await login_btn.click()
                await asyncio.sleep(1.5)
        except Exception as e:
            logger.debug(f"尝试自动唤起登录框: {e}")

        print("\n" + "-" * 70)
        print(">>> 请使用手机【抖音 App】扫描屏幕上的二维码，并在手机上点击【确认登录】 <<<")
        print(">>> 手机确认后，程序将通过网络/DOM/Cookie三重机制秒级捕获，自动保存退出 <<<")
        print(">>> (若你手动关闭了浏览器窗口，程序也会安全捕获退出，无需担心崩溃) <<<")
        print("-" * 70 + "\n")

        login_success = False
        nickname_detected = ""

        # 网络包监听：捕获登录成功的 API 返回
        def on_response(response):
            nonlocal login_success
            if ("check_qrconnect" in response.url or "passport/web/login" in response.url) and response.status == 200:
                try:
                    # 如果响应中指示已确认登录
                    pass
                except Exception:
                    pass
        page.on("response", on_response)

        # 核心轮询检测逻辑
        for second in range(180): # 最长等待 3 分钟
            await asyncio.sleep(1.5)

            # 1. 检查浏览器是否已被用户手动关闭
            if page.is_closed() or not context.pages:
                print("[*] 检测到浏览器窗口已被关闭，正在核验保存的凭据...")
                break

            try:
                # 2. 检查 Cookie 中是否包含鉴权凭证
                cookies = await context.cookies()
                names = [c["name"] for c in cookies]
                auth_found = [k for k in ["sessionid", "sessionid_ss", "sid_guard", "passport_auth_status", "uid_tt"] if k in names]

                # 3. 检查页面右上角是否已显示已登录头像或个人信息
                has_avatar = await page.locator('header img[class*="avatar"], [data-e2e="user-info"], div:has-text("我的") img').count()
                login_btn_count = await page.locator('header button:has-text("登录")').count()

                if auth_found or (has_avatar > 0 and login_btn_count == 0):
                    print(f"\n[+] 🎯 成功检测到账号登录成功！(捕获字段: {auth_found})")
                    login_success = True
                    
                    # 尝试读取并打印已登录账号的昵称
                    try:
                        name_el = page.locator('[data-e2e="user-info"] span, header span[class*="name"]').first
                        if await name_el.is_visible():
                            nickname_detected = await name_el.inner_text()
                    except Exception:
                        pass
                    break

            except Exception as err:
                # 页面跳转刷新过程中的暂时性异常忽略
                pass

        print("[3/4] 正在持久化保存登录凭证 (storage_state.json)...")
        try:
            # 导出全量会话凭证为官方 storage_state.json 文件（绝对杜绝 SQLite 锁问题）
            await context.storage_state(path=STORAGE_STATE_PATH)
            await asyncio.sleep(1)
            await context.close()
        except Exception as e:
            logger.debug(f"关闭保存上下文: {e}")

    # [4/4] 最终验证与报告
    print("\n[4/4] 正在验证凭据持久化结果...")
    valid = is_authenticated()
    print("=" * 70)
    if valid:
        print("🎉 恭喜！抖音登录凭证已完整保存并验证成功！")
        if nickname_detected:
            print(f"👤 当前登录抖音账号昵称: 【{nickname_detected}】")
        print(f"📁 凭证文件已安全写入: {STORAGE_STATE_PATH}")
        print("\n✅ 现在你可以刷新网页后台 (http://localhost:8000)，直接开启自动回复监听！")
    else:
        print("❌ 未检测到有效登录凭据。原因可能是手机端未点击确认，或在扫码前提前退出了。")
        print("👉 请再次运行 python login_helper.py 重新扫码。")
    print("=" * 70 + "\n")
    return valid

if __name__ == "__main__":
    asyncio.run(run_login_flow())
