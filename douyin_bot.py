import asyncio
import logging
import random
import os
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, BrowserContext

from config import BotConfig, FriendConfig, DEFAULT_CONFIG
from storage import MessageStorage
from llm_service import LLMService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DouyinBot")

class DouyinBot:
    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.storage = MessageStorage()
        self.llm = LLMService(self.config)
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def _setup_browser(self, p):
        session_dir = os.path.abspath(self.config.user_data_dir)
        logger.info(f"正在加载浏览器会话: {session_dir}")

        self.context = await p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=self.config.headless,
            viewport={"width": 1366, "height": 850},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ]
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # 注入反爬/指纹防检测脚本
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        """)

    async def _ensure_message_panel_open(self):
        """确保在抖音主页打开了私信面板"""
        try:
            # 检查私信面板容器是否已可见
            is_panel_open = await self.page.evaluate("""
                () => {
                    // 寻找包含私信标题或会话列表的容器
                    const texts = Array.from(document.querySelectorAll('div, span, button'));
                    return texts.some(el => el.innerText && el.innerText.trim() === '私信' && el.offsetParent !== null);
                }
            """)
            
            # 如果还没进入或需要点击私信按钮
            # 常见入口：导航栏“私信”图标或文本
            msg_btn = self.page.locator('xpath=//*[text()="私信" or @data-e2e="header-message"]').first
            if await msg_btn.is_visible():
                logger.info("点击顶部导航栏【私信】按钮打开聊天面板...")
                await msg_btn.click()
                await asyncio.sleep(2)
        except Exception as e:
            logger.debug(f"检查私信面板状态: {e}")

    async def _extract_chat_history(self) -> List[Dict[str, str]]:
        """
        从当前打开的会话窗口中提取历史对话气泡
        利用几何布局（左侧为好友，右侧为自己）通用提取，不强依赖易变的混淆 Class 名
        """
        history = await self.page.evaluate("""
            () => {
                // 1. 尝试找到聊天消息的滚动容器（高度较高、包含多个气泡子元素的容器）
                const potentialContainers = Array.from(document.querySelectorAll('div')).filter(el => {
                    const style = window.getComputedStyle(el);
                    const isScrollable = (style.overflowY === 'auto' || style.overflowY === 'scroll');
                    return isScrollable && el.clientHeight > 200 && el.children.length >= 2;
                });

                if (potentialContainers.length === 0) return [];
                
                // 取最深或最合理的对话容器
                const container = potentialContainers[potentialContainers.length - 1];
                const containerRect = container.getBoundingClientRect();
                const containerMidX = containerRect.left + containerRect.width / 2;

                // 2. 查找气泡行
                const turns = [];
                const allNodes = container.querySelectorAll('*');
                
                // 筛选包含文本且可视的消息块
                for (const node of allNodes) {
                    // 排除系统提示/时间戳标签（通常较短或居中）
                    if (node.children.length === 0 && node.innerText && node.innerText.trim().length > 0) {
                        const text = node.innerText.trim();
                        // 过滤纯时间如 "12:30"、"昨天"
                        if (/^(\\d{1,2}:\\d{2}|昨天|今天|\\d{1,2}月\\d{1,2}日)/.test(text) && text.length < 15) {
                            continue;
                        }

                        const rect = node.getBoundingClientRect();
                        if (rect.width <= 0 || rect.height <= 0) continue;

                        // 依据气泡中心点判断发送人：居中线左侧为好友，右侧为自己
                        const nodeMidX = rect.left + rect.width / 2;
                        const sender = nodeMidX > containerMidX ? 'me' : 'friend';

                        turns.push({
                            sender: sender,
                            content: text,
                            top: rect.top
                        });
                    }
                }

                // 按从上到下顺序排序并去重相邻相同文本
                turns.sort((a, b) => a.top - b.top);
                const uniqueTurns = [];
                for (const t of turns) {
                    if (uniqueTurns.length === 0 || 
                        uniqueTurns[uniqueTurns.length - 1].content !== t.content) {
                        uniqueTurns.push({ sender: t.sender, content: t.content });
                    }
                }
                return uniqueTurns;
            }
        """)
        return history

    async def _send_message(self, text: str):
        """输入内容并发送"""
        try:
            # 寻找输入框：常见为 textarea 或 contenteditable div
            input_box = self.page.locator('textarea, div[contenteditable="true"]').last
            await input_box.wait_for(state="visible", timeout=5000)
            await input_box.click()
            await asyncio.sleep(0.5)

            # 模拟真人输入文本
            await input_box.fill(text)
            await asyncio.sleep(random.uniform(0.5, 1.2))

            # 尝试按 Enter 发送或点击“发送”按钮
            send_btn = self.page.locator('button:has-text("发送"), [data-e2e="im-send-btn"]').first
            if await send_btn.is_visible():
                await send_btn.click()
            else:
                await input_box.press("Enter")
            
            logger.info("消息已成功提交发送！")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"发送消息执行失败: {e}")

    async def process_friend_chat(self, friend_cfg: FriendConfig):
        """处理指定好友的消息监听与回复"""
        try:
            # 1. 在会话列表中寻找该好友的会话项
            friend_item = self.page.locator(f'xpath=//*[contains(text(), "{friend_cfg.nickname}")]').first
            if not await friend_item.is_visible():
                logger.debug(f"当前未在可见会话列表中找到好友: {friend_cfg.nickname}")
                return

            # 点击进入该好友的聊天窗口
            await friend_item.click()
            await asyncio.sleep(1.5)

            # 2. 读取聊天历史
            chat_history = await self._extract_chat_history()
            if not chat_history:
                return

            # 3. 获取最新一条消息
            latest_turn = chat_history[-1]
            
            # 如果最新一条是我自己发的，说明对方还没回，无需操作
            if latest_turn["sender"] == "me":
                return

            latest_content = latest_turn["content"]

            # 4. 检查是否已经回复过这条消息（防重复发送）
            if self.storage.is_replied(friend_cfg.nickname, latest_content):
                return

            logger.info(f"[{friend_cfg.nickname}] 发来新消息: {latest_content}")

            # 5. 模拟真人思考与打字延迟
            delay = random.uniform(*friend_cfg.reply_delay_range)
            logger.info(f"模拟真人思考等待 {delay:.1f} 秒...")
            await asyncio.sleep(delay)

            # 6. 调用 LLM 结合人设与上下文生成回复
            reply_text = await self.llm.generate_reply(friend_cfg, chat_history)
            if not reply_text:
                logger.warning("未能生成有效回复，跳过本次触发")
                return

            logger.info(f"生成风格化回复 -> [{friend_cfg.nickname}]: {reply_text}")

            # 7. 发送消息并写入已回复记录
            await self._send_message(reply_text)
            self.storage.record_reply(friend_cfg.nickname, latest_content, reply_text)

        except Exception as e:
            logger.error(f"处理好友 [{friend_cfg.nickname}] 聊天异常: {e}")

    async def run(self):
        """主循环监听"""
        async with async_playwright() as p:
            await self._setup_browser(p)
            
            logger.info("正在打开抖音网页版...")
            await self.page.goto("https://www.douyin.com/", wait_until="domcontentloaded")
            await asyncio.sleep(4)

            logger.info("开始私信监听循环...")
            while True:
                try:
                    await self._ensure_message_panel_open()

                    for friend_cfg in self.config.target_friends:
                        await self.process_friend_chat(friend_cfg)
                        await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"主监听循环异常: {e}")

                await asyncio.sleep(self.config.poll_interval)

    async def close(self):
        if self.llm:
            await self.llm.close()
        if self.context:
            await self.context.close()

if __name__ == "__main__":
    bot = DouyinBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("收到中断信号，程序安全退出。")
