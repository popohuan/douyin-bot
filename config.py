import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class FriendConfig(BaseModel):
    """针对特定好友的个性化配置"""
    nickname: str = Field(..., description="抖音私信列表中的好友昵称（需保持一致或包含关键词）")
    relationship: str = Field(default="好友", description="你们之间的关系（例如：死党/同事/开黑队友/闺蜜）")
    persona_prompt: str = Field(
        ...,
        description="针对该好友的个性化回复提示词（语气、说话风格、口头禅、emoji习惯）"
    )
    reply_delay_range: tuple[int, int] = Field(
        default=(3, 8),
        description="回复思考/打字延迟时间范围（秒），模拟真人防检测"
    )

class BotConfig(BaseModel):
    """全局 Bot 配置"""
    # 浏览器配置
    user_data_dir: str = Field(default="./douyin_session", description="浏览器 Session 保存目录")
    headless: bool = Field(default=False, description="是否使用无头模式（建议先设为 False 方便观察）")
    
    # 轮询频率
    poll_interval: int = Field(default=5, description="检查新消息间隔时间（秒）")
    
    # LLM 配置
    llm_api_base: str = Field(default=os.getenv("LLM_API_BASE", "https://api.openai.com/v1"), description="OpenAI兼容API端点")
    llm_api_key: str = Field(default=os.getenv("LLM_API_KEY", ""), description="LLM API Key")
    llm_model: str = Field(default=os.getenv("LLM_MODEL", "gpt-4o-mini"), description="模型名称")
    
    # 读取历史消息条数上限
    max_history_turns: int = Field(default=15, description="提取最近多少条历史上下文")

    # 全局通用身份与防穿帮约束
    global_system_instruction: str = Field(
        default="""你现在需要扮演账号主人进行私信聊天回复。
【核心规则】：
1. 坚决禁止表现得像 AI、客服或助手！绝对不要说“有什么可以帮您”、“作为AI”、“请问”等机械套话。
2. 语言极简、生活化、口语化，像在微信或抖音里随意打字回复。
3. 严格参考上下文以及针对该好友的人设设定与语气。
4. 每次只回复 1~2 句话，尽量不使用长篇大论，标点符号尽量少用（可用空格代替句号）。
5. 如果对方发的是表情包、哈哈、或者问答，按照真实好友的反应自然回应。
""",
        description="全局 System Prompt"
    )

    # 监控的目标好友列表
    target_friends: List[FriendConfig] = Field(default_factory=list)

# 默认初始配置示例
DEFAULT_CONFIG = BotConfig(
    target_friends=[
        FriendConfig(
            nickname="好友A昵称",  # 替换为第一个好友的实际昵称
            relationship="大学死党/游戏开黑队友",
            persona_prompt="""说话风格：
- 极其随意，经常互损、开玩笑。
- 常用口头禅：“6”、“笑死”、“稳的”、“真有你的”、“晚上来两把”。
- 遇到打游戏或吃饭话题很积极，其他话题有点懒洋洋。
- 标点符号很少用，偶尔带[流泪][捂脸][狗头]等经典emoji。""",
            reply_delay_range=(3, 7)
        ),
        FriendConfig(
            nickname="好友B昵称",  # 替换为第二个好友的实际昵称
            relationship="关系很好的闺蜜/同好朋友",
            persona_prompt="""说话风格：
- 活泼、共情能力强、热情、说话比较软萌。
- 喜欢发“哈哈哈哈”、“绝了”、“真的假的！”、“贴贴”。
- 喜欢分享好看的视频或者日常吐槽，互动感强。""",
            reply_delay_range=(4, 9)
        )
    ]
)
