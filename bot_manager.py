import asyncio
import logging
import random
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

import database
from llm_service import LLMService
import login_helper

logger = logging.getLogger("BotManager")

class BotManager:
    _instance = None

    def __init__(self):
        self.is_running = False
        self.status_text = "未运行"
        self.last_heartbeat = None
        self.worker_task: Optional[asyncio.Task] = None
        
        self.llm = LLMService()
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.recent_sent_replies = set()
        
        self.session_dir = login_helper.SESSION_DIR
        self.storage_state_path = login_helper.STORAGE_STATE_PATH

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = BotManager()
        return cls._instance

    def has_session(self) -> bool:
        """检查本地是否真正持久化保存了有效的登录凭证"""
        return login_helper.is_authenticated()

    def get_status(self) -> Dict[str, Any]:
        enabled_friends = database.get_enabled_friends()
        return {
            "is_running": self.is_running,
            "status_text": self.status_text,
            "last_heartbeat": self.last_heartbeat,
            "login_status": "已保存登录凭证" if self.has_session() else "未登录",
            "enabled_friends_count": len(enabled_friends)
        }

    async def start(self) -> bool:
        if self.is_running:
            return True
        if not self.has_session():
            logger.warning("未检测到有效登录凭据，请先扫码登录后再启动监听")
            self.status_text = "未检测到有效登录凭证，请先扫码登录"
            return False
        self.is_running = True
        self.status_text = "正在启动浏览器与私信监听循环..."
        logger.info("启动自动回复机器人后台服务...")
        self.worker_task = asyncio.create_task(self._run_loop())
        return True

    async def stop(self) -> bool:
        if not self.is_running:
            return True
        logger.info("正在停止自动回复机器人后台服务...")
        self.status_text = "正在停止..."
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"停止工作协程异常: {e}")
            self.worker_task = None
        await self._cleanup_browser()
        self.status_text = "已停止"
        logger.info("自动回复机器人已完全停止")
        return True

    async def _cleanup_browser(self):
        try:
            if self.context:
                await self.context.close()
                self.context = None
                self.page = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            logger.error(f"清理浏览器上下文异常: {e}")

    async def _ensure_message_panel_open(self) -> bool:
        """确保在抖音主页打开了私信面板/抽屉"""
        if not self.page:
            return False
        try:
            # 0. 检查是否被抖音安全风控拦截（验证码中间页 / 滑块验证码）
            page_title = await self.page.title()
            if "验证码" in page_title or "verify" in self.page.url:
                logger.error("⚠️ 检测到抖音官方安全风控拦截（滑块验证码 / 验证码中间页）！")
                logger.error("💡 提示：若当前处于静默模式 (Headless)，请在控制台【全局与模型设置】将浏览器模式切换为【🖥️ 弹出浏览器窗口 (Headed 模式)】以手动滑动完成验证；或在终端执行 python run_login.py 重新扫码刷新风险评分。")
                self.status_text = "触发滑块验证码拦截，等待验证"
                return False

            # 0.1 自动关闭任何全屏遮罩或新手引导 ("我知道了" / "关闭")
            await self.page.keyboard.press("Escape")
            await self.page.evaluate('''() => {
                const b = Array.from(document.querySelectorAll('button, div, span')).find(el => el.innerText && (el.innerText.trim() === '我知道了' || el.innerText.trim() === '我知道啦' || el.innerText.trim() === '关闭'));
                if (b) b.click();
            }''')

            # 1. 检查私信抽屉或侧边栏是否已经在 DOM 中展开且可见
            is_open = await self.page.evaluate('''() => {
                const items = Array.from(document.querySelectorAll('[data-e2e="conversation-item"], .conversationConversationItemwrapper, [class*="conversationItem"], [data-stack-layer]'));
                return items.some(el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 50 && r.height > 20;
                });
            }''')
            if is_open:
                return True

            # 2. 定位顶部导航栏区域的【消息】入口并点击
            clicked = False
            msg_locator = self.page.locator('div.oi8cIVOq:has-text("消息"), p.phl13lpd:text-is("消息"), [data-e2e="navigation-item"]:has-text("消息")').first
            if await msg_locator.count() > 0 and await msg_locator.is_visible():
                logger.info("已通过精准选择器定位到顶部【消息】入口并点击，正在唤起私信抽屉与微前端模块...")
                await msg_locator.click()
                clicked = True
            else:
                box = await self.page.evaluate('''() => {
                    const els = Array.from(document.querySelectorAll('*')).filter(el => {
                        const r = el.getBoundingClientRect();
                        return r.y < 100 && r.x > 800 && r.width > 15 && r.width < 120 && r.height > 15 && r.height < 70 && el.innerText && el.innerText.includes('消息');
                    });
                    els.sort((a, b) => a.getBoundingClientRect().width - b.getBoundingClientRect().width);
                    if (els.length === 0) return null;
                    const target = els[0];
                    const r = target.getBoundingClientRect();
                    return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), text: target.innerText.trim() };
                }''')
                if box:
                    logger.info(f"已点击顶部【消息】入口 (坐标: {box['x']}, {box['y']})，正在唤起私信抽屉与微前端模块...")
                    await self.page.mouse.click(box['x'], box['y'])
                    clicked = True
                else:
                    logger.warning("未能在页面顶栏找到【消息】按钮，可能主页正在加载中...")
                    return False

            if clicked:
                # 轮询等待抽屉或会话列表出现 (最多等待 12 秒供微前端加载)
                for sec in range(12):
                    await asyncio.sleep(1)
                    opened = await self.page.evaluate('''() => {
                        const layers = document.querySelectorAll('[data-stack-layer], [data-e2e="conversation-item"], .conversationConversationItemwrapper, [class*="conversationItem"]');
                        return Array.from(layers).some(el => {
                            const r = el.getBoundingClientRect();
                            return r.width > 50 && r.height > 20;
                        });
                    }''')
                    if opened:
                        logger.info(f"✅ 私信抽屉与会话列表已在第 {sec+1} 秒成功激活渲染")
                        return True

            return False
        except Exception as e:
            logger.warning(f"唤起私信面板出现提示: {e}")
            return False

    async def _extract_chat_history(self) -> List[Dict[str, str]]:
        """从当前激活的聊天室中精准提取真实历史对话，杜绝列表层穿透与身份混淆"""
        if not self.page:
            return []
        try:
            raw_history = await self.page.evaluate('''() => {
                const editor = document.querySelector('.messageEditorinputArea') || document.querySelector('[contenteditable="true"]');
                if (!editor) return [];

                // 向上找到包含消息列表的主容器 (完全隔离底层的会话列表)
                let chatContainer = editor;
                while (chatContainer && chatContainer.parentElement && chatContainer.getBoundingClientRect().height < 500) {
                    chatContainer = chatContainer.parentElement;
                }
                if (!chatContainer) return [];

                const cRect = chatContainer.getBoundingClientRect();
                const bubbles = [];

                // 1. 优先通过抖音微前端标准的 [data-index] 虚拟列表项提取
                const indexedBoxes = Array.from(chatContainer.querySelectorAll('div[data-index]'));
                if (indexedBoxes.length > 0) {
                    indexedBoxes.forEach(box => {
                        const idx = parseInt(box.getAttribute('data-index') || '-1', 10);
                        // 判断该消息是否来自我方 (isFromMe 类名标记)
                        const isMe = !!box.querySelector('[class*="isFromMe"], [class*="IsFromMe"]') ||
                                     (box.className && (box.className.includes('isFromMe') || box.className.includes('IsFromMe')));

                        // 提取文本内容
                        const textEl = box.querySelector('[class*="pureText"], [class*="textInnerContent"], [class*="bubbleContent"], [data-e2e="msg-item-content"]');
                        if (textEl && textEl.innerText && textEl.innerText.trim().length > 0) {
                            const text = textEl.innerText.trim();
                            // 过滤系统标签与提示
                            if (!['已读', '未读', '送达', '已送达', '下载客户端', '客户端'].includes(text)) {
                                bubbles.push({
                                    index: idx,
                                    sender: isMe ? 'me' : 'friend',
                                    content: text
                                });
                            }
                        }
                    });

                    // 抖音虚拟列表中，data-index=0 是最新消息，data-index 越大越旧
                    // 历史对话按时间正序排列 (旧 -> 新)
                    bubbles.sort((a, b) => b.index - a.index);
                }

                // 2. 兜底方案 (若未能找到带 data-index 的容器)
                if (bubbles.length === 0) {
                    chatContainer.querySelectorAll('*').forEach(el => {
                        if (el.children.length === 0 && el.innerText && el.innerText.trim().length > 0) {
                            const text = el.innerText.trim();
                            if (/^(\\d{1,2}:\\d{2}|昨天|今天|\\d{1,2}月\\d{1,2}日|\\d{2}\\/\\d{2}|\\d+分钟前)/.test(text) && text.length < 15) return;
                            if (['发送', '按 Enter 发送', '快捷回复', '撤回', '表情', '去设置', '消息', '搜索', '下载客户端', '客户端', '已读', '未读', '送达', '已送达'].includes(text)) return;
                            
                            const r = el.getBoundingClientRect();
                            if (r.y > 70 && r.y < editor.getBoundingClientRect().y - 10 && r.height > 10 && r.height < 200) {
                                const isMe = !!el.closest('[class*="isFromMe"], [class*="IsFromMe"]') || (r.right > cRect.x + cRect.width - 70);
                                bubbles.push({
                                    index: 0,
                                    sender: isMe ? 'me' : 'friend',
                                    content: text,
                                    top: Math.round(r.y)
                                });
                            }
                        }
                    });
                    bubbles.sort((a, b) => a.top - b.top);
                }

                // 连续重复项去重
                const unique = [];
                for (const b of bubbles) {
                    if (unique.length === 0 || unique[unique.length - 1].content !== b.content || unique[unique.length - 1].sender !== b.sender) {
                        unique.push({ sender: b.sender, content: b.content });
                    }
                }
                return unique;
            }''')

            # Python 层校验：若消息内容在近期自主回复集合中，强制修正为我方发言
            corrected_history = []
            for item in raw_history:
                sender = item["sender"]
                content = item["content"].strip()
                if content in self.recent_sent_replies:
                    sender = "me"
                corrected_history.append({"sender": sender, "content": content})

            return corrected_history
        except Exception as e:
            logger.error(f"提取会话历史异常: {e}")
            return []

    async def _send_reply(self, text: str):
        """输入回复文本并发送"""
        if not self.page:
            return
        try:
            clean_text = text.strip()
            self.recent_sent_replies.add(clean_text)

            # 物理点击定位聊天详情输入框
            input_pos = await self.page.evaluate('''() => {
                const ed = document.querySelector('[data-stack-layer="chat"] .messageEditorinputArea') ||
                           document.querySelector('.messageEditorinputArea') ||
                           document.querySelector('[contenteditable="true"]') ||
                           document.querySelector('textarea');
                if (!ed) return null;
                const r = ed.getBoundingClientRect();
                return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
            }''')

            if not input_pos:
                input_pos = {'x': 1200, 'y': 845}

            await self.page.mouse.click(input_pos['x'], input_pos['y'])
            await asyncio.sleep(0.3)
            await self.page.keyboard.type(clean_text)
            await asyncio.sleep(random.uniform(0.4, 0.8))
            
            # 1. 优先按 Enter 发送
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(0.8)

            # 2. 检查输入框是否已清空（若未清空，物理点击右下角红色发送按钮）
            has_remaining = await self.page.evaluate('''() => {
                const ed = document.querySelector('.messageEditorinputArea') || document.querySelector('[contenteditable="true"]');
                return ed && ed.innerText && ed.innerText.trim().length > 0;
            }''')
            if has_remaining:
                send_btn_pos = await self.page.evaluate('''() => {
                    const icons = Array.from(document.querySelectorAll('svg, button, div')).filter(el => {
                        const r = el.getBoundingClientRect();
                        return r.x > 1300 && r.y > 800 && r.y < 890 && r.width >= 20 && r.height >= 20;
                    });
                    if (icons.length === 0) return null;
                    const last = icons[icons.length - 1];
                    const r = last.getBoundingClientRect();
                    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
                }''')
                if send_btn_pos:
                    await self.page.mouse.click(send_btn_pos['x'], send_btn_pos['y'])
                    await asyncio.sleep(0.8)

            logger.info("已完成回复输入与发送触发")
        except Exception as e:
            logger.error(f"发送消息异常: {e}")

    async def _process_friend(self, friend: Dict[str, Any]):
        nickname = friend["nickname"]
        if not self.page:
            return

        try:
            # 0. 检查当前是否在任何聊天室内 (必须存在聊天输入框且宽度>100)
            is_in_chat = await self.page.evaluate('''() => {
                const ed = document.querySelector('.messageEditorinputArea') || document.querySelector('[contenteditable="true"]');
                return !!ed && ed.getBoundingClientRect().width > 100;
            }''')

            # 1. 检查是否已经在目标好友专属聊天室内 (检查 StackChatHeader 专用容器)
            current_chat = False
            if is_in_chat:
                current_chat = await self.page.evaluate(f'''() => {{
                    const header = document.querySelector('[class*="StackChatHeader"], [class*="ChatHeader"]');
                    return !!header && header.innerText.includes('{nickname}');
                }}''')

            if not current_chat:
                if is_in_chat:
                    # 正处于其他好友聊天室，点击返回按钮返回列表 (使用 DOM 直接触发与坐标点击避开未读数徽标遮挡)
                    back_pos = await self.page.evaluate('''() => {
                        const btn = document.querySelector('[class*="StackTitleBarbackBtn"], [class*="TitleBarbackBtn"], [class*="StackTitleBarleftArea"]');
                        if (btn) {
                            if (typeof btn.click === 'function') btn.click();
                            const r = btn.getBoundingClientRect();
                            return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
                        }
                        return { x: 1106, y: 80 };
                    }''')
                    if back_pos:
                        await self.page.mouse.click(back_pos['x'], back_pos['y'])
                    
                    # 等待退出聊天室，回到纯列表 (输入框完全消失)
                    for _ in range(8):
                        await asyncio.sleep(0.4)
                        still_in = await self.page.evaluate('''() => {
                            const ed = document.querySelector('.messageEditorinputArea') || document.querySelector('[contenteditable="true"]');
                            return !!ed && ed.getBoundingClientRect().width > 100;
                        }''')
                        if not still_in:
                            break
                        if _ == 3:
                            await self.page.mouse.click(1106, 80)

                # 此时在会话列表，寻找目标好友的条目
                box_pos = None
                for _ in range(6):
                    box_pos = await self.page.evaluate(f'''() => {{
                        const items = Array.from(document.querySelectorAll('[data-e2e="conversation-item"], .conversationConversationItemwrapper, [class*="conversationItem"]'));
                        const target = items.find(el => {{
                            const r = el.getBoundingClientRect();
                            return r.width > 100 && r.height > 30 && r.height < 120 && el.innerText && el.innerText.includes('{nickname}');
                        }});
                        if (!target) return null;
                        const r = target.getBoundingClientRect();
                        return {{ x: Math.round(r.x + 50), y: Math.round(r.y + r.height / 2) }};
                    }}''')
                    if box_pos:
                        break
                    await asyncio.sleep(0.8)

                if not box_pos:
                    logger.debug(f"好友 [{nickname}] 尚未出现在当前可视会话列表中")
                    return

                logger.info(f"🎯 检测到指定好友 [{nickname}] 会话条目，点击进入对话...")
                await self.page.mouse.click(box_pos['x'], box_pos['y'])

                # 严格等待并核验聊天室头部标题
                verified = False
                for _ in range(8):
                    await asyncio.sleep(0.5)
                    verified = await self.page.evaluate(f'''() => {{
                        const header = document.querySelector('[class*="StackChatHeader"], [class*="ChatHeader"]');
                        return !!header && header.innerText.includes('{nickname}');
                    }}''')
                    if verified:
                        break

                if not verified:
                    logger.warning(f"未能确认已进入好友 [{nickname}] 的专属聊天室，跳过本次处理以防串话")
                    return

            # 双重保险：提取前再次核验顶栏是否属于该好友
            in_target_chat = await self.page.evaluate(f'''() => {{
                const header = document.querySelector('[class*="StackChatHeader"], [class*="ChatHeader"]');
                return !!header && header.innerText.includes('{nickname}');
            }}''')
            if not in_target_chat:
                logger.warning(f"当前激活窗口顶栏并非好友 [{nickname}]，跳过提取")
                return

            # 2. 提取当前聊天上下文
            chat_history = await self._extract_chat_history()
            if not chat_history:
                logger.info(f"[{nickname}] 尚未提取到有效气泡消息")
                return

            # 2.1 智能同步归档到该好友的历史对话档案库
            try:
                new_archived_cnt = database.archive_chat_messages(nickname, chat_history)
                if new_archived_cnt > 0:
                    logger.info(f"[{nickname}] 历史档案库已智能归档新增 {new_archived_cnt} 条消息记录")
            except Exception as arc_e:
                logger.warning(f"[{nickname}] 历史消息归档异常: {arc_e}")

            latest_turn = chat_history[-1]
            logger.info(f"[{nickname}] 成功读取到历史对话 {len(chat_history)} 轮 | 最新一条: [{latest_turn['sender']}] 「{latest_turn['content'][:25]}」")

            # 3. 若最新一条是我发的，对方未回，无需回复
            if latest_turn["sender"] == "me":
                logger.info(f"[{nickname}] 最新一条为我方发言，静候对方回复中...")
                return

            latest_content = latest_turn["content"]
            # 4. 防重复判断
            if database.is_replied(nickname, latest_content):
                logger.info(f"[{nickname}] 消息「{latest_content[:20]}」在已回复缓存中，无需重复回复")
                return

            logger.info(f"🔔 [{nickname}] 收到新私信: 【{latest_content}】")
            self.status_text = f"正在回复好友 [{nickname}]..."

            # 5. 模拟真人思考与打字延迟
            delay_min = friend.get("reply_delay_min", 3)
            delay_max = friend.get("reply_delay_max", 8)
            delay = random.uniform(delay_min, delay_max)
            logger.info(f"[{nickname}] 模拟真人输入思考延迟: {delay:.1f} 秒...")
            await asyncio.sleep(delay)

            # 6. 从持久化档案库获取长效记忆上下文 (融合当前屏幕气泡与历史存档)
            settings = database.get_all_settings()
            max_turns = int(settings.get("max_history_turns", 20))
            persisted_history = database.get_friend_chat_history(nickname, limit=max_turns)
            full_context = persisted_history if persisted_history else chat_history

            # 调用 LLM 注入知识库、人设与全量深度上下文记忆
            reply_text = await self.llm.generate_reply(friend, full_context)
            if not reply_text:
                logger.warning(f"[{nickname}] LLM 未能生成有效回复内容")
                return

            logger.info(f"✨ 成功生成回复 -> [{nickname}]: {reply_text}")
            await self._send_reply(reply_text)
            
            # 发送成功后立即将我方回复沉淀入好友历史档案库
            database.append_chat_message(nickname, "me", reply_text)
            database.record_reply_log(nickname, latest_content, reply_text)
            self.status_text = f"已回复 [{nickname}]"
            logger.info(f"✅ 消息已成功发送至 [{nickname}] 并已归档沉淀长效记忆")

        except Exception as e:
            logger.error(f"处理好友 [{nickname}] 会话异常: {e}")

    async def _run_loop(self):
        """核心后台轮询协程"""
        settings = database.get_all_settings()
        headless_setting = settings.get("headless", "false").lower() == "true"
        poll_interval = int(settings.get("poll_interval", 5))

        logger.info(f"正在启动 Playwright 引擎 (Headless={headless_setting}, 轮询间隔={poll_interval}s)...")
        login_helper.clean_locks()
        
        try:
            self.playwright = await async_playwright().start()
            
            chromium_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
            ]
            
            # 若启用无头模式，采用现代 Chromium 隐形架构 (--headless=new)，彻底规避 SecSDK 无头滑块风控
            if headless_setting:
                chromium_args.append("--headless=new")
                launch_headless = False
            else:
                launch_headless = False

            # 使用 launch_persistent_context 完美挂载 IndexedDB 与全量会话凭证
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.session_dir,
                headless=launch_headless,
                viewport={"width": 1440, "height": 900},
                args=chromium_args
            )

            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            logger.info("正在导航至抖音官网 (https://www.douyin.com/)...")
            try:
                await self.page.goto("https://www.douyin.com/", wait_until="commit", timeout=25000)
            except Exception as nav_e:
                logger.debug(f"导航提示: {nav_e}")

            # 等待主页水合与基础组件渲染 (平稳等待 SPA 路由与微前端初始化)
            logger.info("等待页面水合与基础组件渲染...")
            await asyncio.sleep(2)
            for _ in range(15):
                try:
                    page_title = await self.page.title()
                    if "验证码" in page_title or "verify" in self.page.url:
                        logger.error("⚠️ 检测到安全风控拦截（滑块验证码）！请在前端【系统与模型配置】将浏览器模式切换为【🖥️ 弹出浏览器窗口】并完成滑块，或执行扫码登录。")
                        self.status_text = "触发安全拦截（滑块验证码）"
                        break
                    ready = await self.page.evaluate('''() => {
                        const msgEl = Array.from(document.querySelectorAll('*')).find(el => {
                            const r = el.getBoundingClientRect();
                            return r.y < 100 && r.x > 800 && el.innerText && el.innerText.includes('消息');
                        });
                        return !!msgEl;
                    }''')
                    if ready:
                        break
                except Exception as eval_e:
                    logger.debug(f"水合检测平稳重试中: {eval_e}")
                await asyncio.sleep(1)

            logger.info("抖音主页加载完成，进入私信轮询监控...")

            while self.is_running:
                try:
                    self.last_heartbeat = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 确保私信面板打开
                    panel_open = await self._ensure_message_panel_open()
                    if not panel_open:
                        logger.warning("私信面板未处于激活状态，等待下个轮询周期重试...")
                        await asyncio.sleep(poll_interval)
                        continue

                    # 动态获取已启用的好友计划
                    enabled_friends = database.get_enabled_friends()
                    if not enabled_friends:
                        self.status_text = "运行中 (未启用任何好友回复计划)"
                    else:
                        for friend in enabled_friends:
                            if not self.is_running:
                                break
                            await self._process_friend(friend)
                            await asyncio.sleep(1.5)
                        self.status_text = f"监听运行中 (监控好友数: {len(enabled_friends)})"

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"轮询监听处理异常: {e}")
                    self.status_text = f"轮询异常: {e}"

                await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            pass
        except Exception as fatal_e:
            logger.error(f"机器人后台运行发生严重错误: {fatal_e}", exc_info=True)
            self.status_text = f"运行报错: {fatal_e}"
        finally:
            await self._cleanup_browser()
            self.is_running = False
            logger.info("后台监听循环已退出")
