import logging
from typing import List, Dict, Any, Optional
import httpx
import database

logger = logging.getLogger("LLMService")

class LLMService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate_reply(
        self,
        friend_dict: Dict[str, Any],
        chat_history: List[Dict[str, str]]
    ) -> str:
        """
        基于历史对话、好友专属资料库与人设提示词生成风格化回复
        :param friend_dict: 来自数据库的好友配置字典
        :param chat_history: 历史消息列表 [{"sender": "friend"|"me", "content": "..."}]
        """
        settings = database.get_all_settings()
        api_base = settings.get("llm_api_base", "https://api.deepseek.com/v1").rstrip("/")
        api_key = settings.get("llm_api_key", "").strip()
        model = settings.get("llm_model", "deepseek-chat")
        max_turns = int(settings.get("max_history_turns", 50))
        global_instruction = settings.get("global_instruction", "").strip() or database.DEFAULT_GLOBAL_INSTRUCTION

        if not api_key:
            logger.error("LLM API Key 未配置，请在后台设置中填写！")
            return ""

        # 组织专属资料库与记忆块
        kb_text = (friend_dict.get("knowledge_base") or database.DEFAULT_KNOWLEDGE_BASE).strip()
        kb_section = ""
        if kb_text:
            kb_section = f"""
【关于该好友的专属背景资料库/事实备忘】：
{kb_text}
（请牢记上述事实。当对方聊到相关话题、共同经历或偏好时，自然体现出熟知程度，切勿违背或胡编乱造）
"""

        # 组织系统提示词
        persona_text = (friend_dict.get("persona_prompt") or database.DEFAULT_PERSONA_PROMPT).strip()
        system_content = f"""{global_instruction}

【当前聊天对象关系】：{friend_dict.get('relationship', '恋人/同好朋友')}
【该好友的专属人设与说话风格要求】：
{persona_text}
{kb_section}
【长效历史对话记忆与上下文要求】：
这是你与该好友 [{friend_dict.get('nickname', '')}] 的连续历史对话记录（包括之前的聊天与回答）。
你必须保持记忆与话题的连续性，对之前聊过的事实、约定、话题自然承接，切忌遗忘或自相矛盾。
请根据历史上下文、专属人设和事实资料库，自然地生成你的下一句回复。输出纯文本，不要包含任何前缀（如“我：”或“回复：”）。
"""

        messages = [{"role": "system", "content": system_content}]

        # 截取最近历史对话
        sliced_history = chat_history[-max_turns:]
        for turn in sliced_history:
            role = "assistant" if turn["sender"] == "me" else "user"
            messages.append({
                "role": role,
                "content": turn["content"]
            })

        # 校验最后一轮是否为用户发言
        if not messages or messages[-1]["role"] != "user":
            logger.warning("历史消息最后一项非对方发言，放弃生成")
            return ""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 160
        }

        try:
            url = f"{api_base}/chat/completions"
            response = await self.client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                logger.error(f"LLM API 响应异常 HTTP {response.status_code}: {response.text}")
                return ""

            res_json = response.json()
            reply = res_json["choices"][0]["message"]["content"].strip()

            # 去除可能的角色前缀
            for prefix in ["我：", "我:", "回复：", "回复:"]:
                if reply.startswith(prefix):
                    reply = reply[len(prefix):].strip()

            return reply
        except Exception as e:
            logger.error(f"调用 LLM 发生异常: {e}")
            return ""

    async def close(self):
        await self.client.aclose()
