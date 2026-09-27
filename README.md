# 🤖 抖音高拟真自动回复 & 赛博哄女友替身机器人 (Douyin Girlfriend Bot)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Playwright-Chromium-green?logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/FastAPI-Modern%20API-teal?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue.js-3.x-emerald?logo=vue.js&logoColor=white" alt="Vue3">
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20%2F%20OpenAI-purple?logo=openai&logoColor=white" alt="LLM Support">
  <img src="https://img.shields.io/badge/License-MIT-amber" alt="License MIT">
</p>

<p align="center">
  <b>基于 DeepSeek 大模型 + Playwright 真实持久化浏览器驱动的抖音（PC 网页端）自动化高拟人私信替身系统。</b><br>
  配备全时空现实人类锚定系统、多轮长效历史对话归档、专属事实记忆库、防穿帮缓兵协议与现代化 Web 单页管理控制台。
</p>

---

## 💡 为什么需要它？

很多恋人、好友习惯在抖音上分享搞笑视频、生活碎片与即时查岗（*“在干嘛呢”、“你看这个小狗好搞笑”、“今晚吃什么”*）。  
如果打游戏或写代码时未能及时回复，往往演变成送命题；但如果套用常规的人工客服或粗制滥造的 Bot，冷冰冰的“亲亲/有什么可以帮您”或胡编现实细节则会**直接物理级穿帮**。

本项目从微前端逆向与拟人化认知心理学出发，彻底解决**抗风控、防死循环、深层记忆丢失、机械味浓重与即时现实穿帮**等核心痛点，打造一个真实度达 99.9% 的“高情商赛博替身”。

---

## ✨ 核心核心杀手级亮点

### 1. 🕒 全时空现实人类锚定系统（Spatiotemporal & Circadian Engine）
将真实物理世界的时空感无感渗透进大模型潜意识，彻底消除“算力怪物”的违和感：
- **生物钟与时段感知**：早晨起床气、上午工作平稳、午休外卖犯困、下午低血糖摸鱼、傍晚下班通勤路噪、深夜感性吐槽；
- **日历心理学**：周一厌班、周五狂喜、调休痛苦、节假日关注放假与出行（绝不发政企拜年短信）；
- **微气候体感**：转换为冷风灌脖子、下雨湿鞋、天热空调续命等体感，绝不机械报天气预报；
- **IM 排版与标点脱敏**：消灭 Markdown 与加粗，以空格代替逗号，句尾不带句号，短句自然换行。

### 2. 🧠 最长公共后缀滑动窗口长效记忆归档（Sequence Alignment Memory）
针对抖音 PC 端 IM 虚拟滚动列表（Virtual List）仅在 DOM 保留当前视口约 10 条气泡的特性：
- 采用最长公共后缀-前缀对齐算法（Longest Common Suffix-Prefix Alignment），实现零重复、严格幂等的增量入库；
- 每次生成回复前，从 SQLite 调取多达 **50 轮深度持久化上下文**喂给大模型，彻底杜绝“金鱼脑”与上下文断层。

### 3. 🛡️ 终极防穿帮缓兵协议（Anti-Leak Failsafe）
- **高危查岗（你在哪/在干嘛）**：严格依当前时段打太极（“在摸鱼看文档呢”、“正在偷吃外卖”），绝不凭空瞎编现实地点；
- **私密回忆/找东西（我钥匙在哪）**：拖延战术应对（“手头正忙着，待会儿到家了翻给你看”）；
- **情绪严重红线**：若对方出现严重哭泣、吵架，自动触发缓兵话术并为真人接管争取介入时间。

### 4. 🪟 独立弹窗可视化扫码登录（Popup Login Helper）
- 双击即可唤起独立的 1280x820 Chrome 窗口并**自动点击网页右上角【登录】居中调出大号二维码**；
- 手机抖音扫码确认后，毫秒级捕获认证 Cookie 与 Token，自动安全落盘持久化退出。

### 5. 🖥️ 现代化 Web 单页管理看板（FastAPI + Vue3 + Tailwind CSS）
- **多好友独立方案**：每个好友独立配置专属说话风格、关系定位、事实资料库与思考延迟；
- **沉浸式对话记忆抽屉**：可视化聊天时间轴、关键词实时检索、单条消息修剪、**人工先验记忆注入**；
- **实时终端与数据全生命周期管理**：WebSocket/轮询实时运行日志流、配置备份导出导入、敏感会话凭据物理粉碎。

---

## 🏗️ 系统架构图

```mermaid
flowchart TD
    A["Web 用户控制台 (FastAPI + Vue3 + Tailwind)"] --> B["配置管理 & 存储层 (SQLite 数据库)"]
    A --> C["调度中枢 (BotManager 单例协程循环)"]
    
    subgraph CoreLoop ["BotManager 监听主循环"]
        C --> D["抽屉唤起 & 微前端保活 (_ensure_message_panel_open)"]
        D --> E["会话列表目标精准匹配 (_process_friend)"]
        E --> F["聊天室气泡提取 (_extract_chat_history)"]
        F --> G["滑动窗口后缀对齐增量归档 (archive_chat_messages)"]
        G -- "收到好友新消息" --> H["拟人推理引擎 (LLMService)"]
        H --> I["真实物理输入与双重发送 (_send_reply)"]
    end
    
    subgraph BrowserLayer ["浏览器底层环境 (Playwright)"]
        E -. 物理坐标点击 .-> J["Chromium Persistent Context"]
        I -. 键盘打字与回车 .-> J
        J --> K["官方抖音网页主站 (douyin.com)"]
    end
```

---

## 🚀 极速上手体验

### 1. 环境准备与依赖安装
确保本地安装有 **Python 3.10 或更高版本**：
```bash
# 克隆仓库
git clone https://github.com/popohuan/douyin-girlfriend-bot.git
cd douyin-girlfriend-bot

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器内核
playwright install chromium
```

### 2. 扫码登录抖音账号
系统提供了一键弹窗扫码向导：
- **Windows 用户**：直接双击根目录下的 **`login_browser.bat`**；
- **命令行用户**：执行 `python -X utf8 login_browser.py`；
- 电脑将自动拉起 Chrome 浏览器并唤起登录二维码，打开手机【抖音 App】扫码并确认登录即可。

### 3. 启动管理控制台
- **Windows 用户**：双击 **`start_windows.bat`**；
- **Linux / macOS 用户**：执行 `./start_linux.sh` 或 `python -X utf8 server.py`；
- 打开浏览器访问管理后台：  
  👉 **`http://127.0.0.1:8000`**

### 4. 填入 API Key 与开启监听
1. 进入 **【全局与模型设置】**，填写你的 **DeepSeek API Key**（或任何兼容 OpenAI 格式的模型密钥），点击保存；
2. 进入 **【好友计划 & 专属资料库】**，添加或修改好友昵称（需与抖音好友昵称完全一致），选择或自定义人设模版；
3. 点击顶部右上角绿色的 **【启动监听】**，系统即刻进入全自动高拟人回复监控！

---

## 📂 项目文件结构

```text
douyin-girlfriend-bot/
├── server.py                        # FastAPI 服务端，提供 RESTful API 与静态页面挂载
├── bot_manager.py                   # Playwright 调度中枢，实现微前端保活、气泡提取与发送
├── database.py                      # SQLite 持久层，含序列对齐算法、长效历史与出厂预设
├── llm_service.py                   # 拟人大模型推理中枢，动态装配四层 Prompt 与历史切片
├── login_browser.py                 # 可视化弹窗扫码登录向导 (Python)
├── login_browser.bat                # Windows 一键双击扫码登录快捷方式
├── login_helper.py                  # 底层登录凭据捕获、Cookie 导出与校验库
├── run_login.py                     # CLI 登录与凭据清理入口
├── package_project.py               # 项目脱敏全量打包工具
├── requirements.txt                 # Python 依赖清单
├── start_windows.bat                # Windows 一键启动服务
├── start_linux.sh                   # Linux / VPS 启动脚本
├── USAGE_GUIDE.md                   # 详细使用操作与实战手册
├── ARCHITECTURE_AND_IMPLEMENTATION.md # 全链路架构逆向与攻坚演进文档
├── static/
│   └── index.html                   # Vue3 + Tailwind CSS 单页现代化管理控制台
├── LICENSE                          # MIT 开源许可证
└── README.md                        # 项目主文档
```

---

## ⚙️ 内置官方预设模版

本系统出厂预置了经过实战检验的高拟真人设与事实档案模版，可在 Web 控制台一键套用：
1. **【年下男友/恋人】**：浓郁少年感、松弛粘人与偶尔嘴硬，口语倒装，内置防查岗打太极与两人专属生活习惯/黑历史档案；
2. **【亲弟血脉压制】**：极度冷漠嘲讽、惜字如金，专供拦截借钱与查岗踢皮球战术；
3. **【开黑死党】**：互损随意、口头禅“6/笑死/稳”、宵夜与游戏默契。

---

## 📖 深度进阶文档

- [完整使用操作指南 (USAGE_GUIDE.md)](USAGE_GUIDE.md)：涵盖环境部署、后台操作、历史对话管理、VPS 长期静默挂机（Systemd）与排查手册；
- [全链路架构与逆向攻坚历程 (ARCHITECTURE_AND_IMPLEMENTATION.md)](ARCHITECTURE_AND_IMPLEMENTATION.md)：复盘微前端 DOM 虚拟列表、React 18 合成事件、中轴线判定、会话穿透等七大技术死穴的攻坚全过程。

---

## ⚠️ 免责声明 (Disclaimer)

1. 本项目仅供 Python 自动化技术学习、大模型拟人化 Prompt 工程设计与前端 DOM 交互研究交流使用；
2. 请合理设置打字延迟与轮询时间，切勿用于批量垃圾消息营销或任何违反平台服务条款的行为；
3. **友情提示**：AI 终究是辅助，真诚沟通才是感情长久的基石。若因大模型即兴发挥导致感情纠纷、跪搓衣板等不可抗力事故，作者概不负责 😂。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。欢迎 Star、Fork 与提 Issue 交流！
