import os
import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import database
from bot_manager import BotManager

# 配置日志捕获内存环形缓冲区 (最近 200 条系统日志)
system_logs_buffer = deque(maxlen=200)

class BufferLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            system_logs_buffer.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": record.levelname,
                "message": msg
            })
        except Exception:
            pass

# 初始化日志器
logger = logging.getLogger()
logger.setLevel(logging.INFO)
buffer_handler = BufferLogHandler()
buffer_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(buffer_handler)

# 初始化数据库
database.init_db()

app = FastAPI(title="抖音自动回复后台管理系统", version="1.0.0")

bot_manager = BotManager.get_instance()

# 静态资源挂载
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

# --- 状态与控制 API ---
@app.get("/api/status")
async def get_bot_status():
    return bot_manager.get_status()

@app.post("/api/bot/start")
async def start_bot():
    if not bot_manager.has_session():
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "尚未检测到有效登录凭证，请先扫码登录！"}
        )
    success = await bot_manager.start()
    return {"success": success, "status": bot_manager.get_status()}

@app.post("/api/bot/stop")
async def stop_bot():
    success = await bot_manager.stop()
    return {"success": success, "status": bot_manager.get_status()}

@app.post("/api/bot/logout")
async def logout_bot():
    """退出登录并清理凭证，支持切换账号"""
    if bot_manager.is_running:
        await bot_manager.stop()
    import login_helper
    login_helper.clear_session(backup=True)
    return {"success": True, "message": "已成功清除当前登录凭据并备份旧凭据，现在可以扫码登录新账号！"}

@app.post("/api/bot/credentials/clear")
async def clear_credentials():
    """彻底清除所有个人登录凭据与会话备份，零隐私残留"""
    if bot_manager.is_running:
        await bot_manager.stop()
    import login_helper
    result = login_helper.wipe_all_credentials()
    return {
        "success": True, 
        "message": "已彻底销毁所有本地个人登录凭证与会话备份，零隐私残留！", 
        "details": result,
        "status": bot_manager.get_status()
    }

@app.post("/api/bot/login/popup")
async def popup_login(switch: bool = False):
    """在当前电脑上直接弹出 Chrome 窗口扫码登录"""
    if bot_manager.is_running:
        await bot_manager.stop()
    import login_helper
    # 异步非阻塞执行登录流
    asyncio.create_task(login_helper.run_login_flow(clear_session_first=switch))
    return {"success": True, "message": "已为你拉起 Chrome 浏览器并唤起登录二维码，请使用手机【抖音 App】扫码！"}

# --- 好友计划 CRUD API ---
class FriendCreateUpdateModel(BaseModel):
    nickname: str = Field(..., description="抖音好友昵称")
    relationship: str = Field(default="好友", description="关系")
    persona_prompt: str = Field(..., description="回复人设提示词")
    knowledge_base: Optional[str] = Field(default="", description="专属资料库/记忆")
    reply_delay_min: int = Field(default=3, description="最小思考延迟")
    reply_delay_max: int = Field(default=8, description="最大思考延迟")
    is_enabled: int = Field(default=1, description="1开启 0关闭")

@app.get("/api/friends")
async def get_friends():
    return database.list_friends()

@app.post("/api/friends")
async def add_friend(data: FriendCreateUpdateModel):
    try:
        new_id = database.create_friend(data.model_dump())
        return {"success": True, "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/friends/{friend_id}")
async def update_friend(friend_id: int, data: FriendCreateUpdateModel):
    friend = database.get_friend_by_id(friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="好友计划不存在")
    database.update_friend(friend_id, data.model_dump())
    return {"success": True}

@app.delete("/api/friends/{friend_id}")
async def delete_friend(friend_id: int):
    database.delete_friend(friend_id)
    return {"success": True}

@app.post("/api/friends/{friend_id}/toggle")
async def toggle_friend(friend_id: int):
    friend = database.get_friend_by_id(friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="好友计划不存在")
    new_status = 0 if friend["is_enabled"] == 1 else 1
    database.toggle_friend_status(friend_id, new_status)
    return {"success": True, "is_enabled": new_status}

# --- 好友历史对话档案与记忆 API ---
class ChatMessageCreateModel(BaseModel):
    sender: str = Field(default="friend", description="'friend' 或 'me'")
    content: str = Field(..., description="消息文本内容")

@app.get("/api/friends/{friend_id}/chat_history")
async def get_friend_chat_history(friend_id: int, limit: int = 150):
    """获取指定好友的持久化历史对话存档（按时间正序）"""
    friend = database.get_friend_by_id(friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="好友计划不存在")
    history = database.get_friend_chat_history(friend["nickname"], limit=limit)
    return {
        "success": True,
        "friend": friend,
        "history": history,
        "count": len(history)
    }

@app.post("/api/friends/{friend_id}/chat_history")
async def add_friend_chat_history(friend_id: int, data: ChatMessageCreateModel):
    """手动为好友追加一条历史记忆或过去的真实聊天记录"""
    friend = database.get_friend_by_id(friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="好友计划不存在")
    msg_id = database.append_chat_message(friend["nickname"], data.sender, data.content)
    return {"success": True, "id": msg_id, "message": "已成功追加历史对话记录"}

@app.delete("/api/friends/{friend_id}/chat_history")
async def clear_friend_chat_history(friend_id: int):
    """清空指定好友的历史对话存档"""
    friend = database.get_friend_by_id(friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="好友计划不存在")
    count = database.clear_friend_chat_history(friend["nickname"])
    return {"success": True, "message": f"已清空好友 [{friend['nickname']}] 的 {count} 条历史对话存档"}

@app.delete("/api/chat_history/message/{msg_id}")
async def delete_chat_message(msg_id: int):
    """删除单条历史存档消息"""
    success = database.delete_chat_message(msg_id)
    if not success:
        raise HTTPException(status_code=404, detail="该条历史消息不存在")
    return {"success": True, "message": "已删除该条历史消息"}

@app.get("/api/chat_history/stats")
async def get_chat_history_stats():
    """获取各好友历史对话存档统计"""
    stats = database.get_chat_history_stats()
    return {"success": True, "stats": stats}

@app.delete("/api/chat_history/clear_all")
async def clear_all_chat_history():
    """清空全部好友的历史对话存档"""
    count = database.clear_all_chat_history()
    return {"success": True, "message": f"已成功清空所有好友共 {count} 条历史对话存档"}

@app.get("/api/data/export/chat_history")
async def export_chat_history(format: str = "json", friend_id: Optional[int] = None):
    """导出好友历史对话记录存档数据 (支持 txt 与 json)"""
    import json
    from fastapi.responses import Response
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if friend_id:
        friend = database.get_friend_by_id(friend_id)
        if not friend:
            raise HTTPException(status_code=404, detail="好友计划不存在")
        history = database.get_friend_chat_history(friend["nickname"], limit=2000)
        filename_prefix = f"chat_history_{friend['nickname']}"
    else:
        friends = database.list_friends()
        history = []
        for f in friends:
            h = database.get_friend_chat_history(f["nickname"], limit=2000)
            history.extend(h)
        filename_prefix = "chat_history_all"

    if format.lower() == "txt":
        lines = []
        for item in history:
            sender_label = "我方回复" if item["sender"] == "me" else f"对方 ({item.get('friend_nickname', '')})"
            lines.append(f"[{item.get('created_at', '')}] {sender_label}:\n{item.get('content', '')}\n")
        content = "\n".join(lines)
        return Response(
            content=content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename_prefix}_{timestamp}.txt"}
        )
    else:
        content = json.dumps(history, ensure_ascii=False, indent=2)
        return Response(
            content=content.encode("utf-8"),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename_prefix}_{timestamp}.json"}
        )

# --- 系统配置 API ---
@app.get("/api/settings")
async def get_settings():
    return database.get_all_settings()

@app.post("/api/settings")
async def save_settings(settings: Dict[str, Any]):
    database.update_settings(settings)
    return {"success": True}

@app.get("/api/presets/templates")
async def get_preset_templates():
    return {
        "default_global_instruction": database.DEFAULT_GLOBAL_INSTRUCTION,
        "default_persona_prompt": database.DEFAULT_PERSONA_PROMPT,
        "default_knowledge_base": database.DEFAULT_KNOWLEDGE_BASE,
        "templates": {
            "boyfriend": {
                "name": "年下男友 / 恋人同好",
                "relationship": "恋人/同好朋友",
                "persona_prompt": database.DEFAULT_PERSONA_PROMPT,
                "knowledge_base": database.DEFAULT_KNOWLEDGE_BASE,
                "reply_delay_min": 4,
                "reply_delay_max": 9
            },
            "brother": {
                "name": "亲弟 / 血脉压制毒舌",
                "relationship": "弟弟",
                "persona_prompt": database.DEFAULT_BROTHER_PERSONA_PROMPT,
                "knowledge_base": database.DEFAULT_BROTHER_KNOWLEDGE_BASE,
                "reply_delay_min": 3,
                "reply_delay_max": 8
            }
        }
    }

@app.post("/api/settings/reset_defaults")
async def reset_settings_defaults():
    database.update_settings({
        "global_instruction": database.DEFAULT_GLOBAL_INSTRUCTION,
        "max_history_turns": "50",
        "poll_interval": "10"
    })
    return {"success": True, "message": "已将全局拟人规则及系统参数恢复为官方最高预设"}

# --- 日志记录 API ---
@app.get("/api/logs")
async def get_logs(limit: int = 100):
    return database.get_recent_logs(limit)

@app.delete("/api/logs/{log_id}")
async def delete_log(log_id: int):
    """删除单条历史对话回复记录"""
    success = database.delete_reply_log(log_id)
    if not success:
        raise HTTPException(status_code=404, detail="指定日志不存在")
    return {"success": True, "message": "已删除该条回复记录"}

@app.post("/api/logs/clear")
async def clear_all_logs():
    """清空所有历史对话回复记录及去重缓存"""
    count = database.clear_reply_logs()
    return {"success": True, "message": f"已成功清空 {count} 条历史回复记录与去重缓存！"}

# --- 数据保存与删除 API ---
@app.get("/api/data/export/logs")
async def export_logs(format: str = "json"):
    """导出历史回复记录数据 (支持 json 与 csv 格式保存)"""
    import json
    from fastapi.responses import Response
    logs = database.get_all_reply_logs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format.lower() == "csv":
        import io
        import csv
        output = io.StringIO()
        output.write('\ufeff')  # UTF-8 BOM
        writer = csv.writer(output)
        writer.writerow(["ID", "时间", "好友昵称", "对方消息内容", "Bot风格化回复"])
        for row in logs:
            writer.writerow([row["id"], row["created_at"], row["friend_nickname"], row["incoming_msg"], row["reply_content"]])
        return Response(
            content=output.getvalue().encode('utf-8'),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=reply_logs_{timestamp}.csv"}
        )
    else:
        content = json.dumps(logs, ensure_ascii=False, indent=2)
        return Response(
            content=content.encode('utf-8'),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=reply_logs_{timestamp}.json"}
        )

@app.get("/api/data/export/friends")
async def export_friends():
    """导出好友配置方案为 JSON 备份文件"""
    import json
    from fastapi.responses import Response
    friends = database.list_friends()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    content = json.dumps(friends, ensure_ascii=False, indent=2)
    return Response(
        content=content.encode('utf-8'),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=friends_backup_{timestamp}.json"}
    )

@app.post("/api/data/import/friends")
async def import_friends(friends_list: List[Dict[str, Any]]):
    """批量导入/恢复好友配置方案"""
    if not isinstance(friends_list, list):
        raise HTTPException(status_code=400, detail="导入数据格式需为好友对象数组")
    count = database.import_friends_data(friends_list)
    return {"success": True, "message": f"成功导入/更新 {count} 位好友回复方案！"}

@app.post("/api/data/clear/friends")
async def clear_all_friends():
    """批量清空所有好友计划"""
    count = database.clear_all_friends()
    return {"success": True, "message": f"已成功删除所有好友回复方案 (共 {count} 条)！"}

@app.get("/api/data/backup/database")
async def backup_database():
    """完整备份并下载 SQLite 数据库文件 (bot_douyin.db)"""
    db_file = os.path.abspath(database.DB_PATH)
    if not os.path.exists(db_file):
        raise HTTPException(status_code=404, detail="数据库文件不存在")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return FileResponse(
        path=db_file,
        filename=f"bot_douyin_backup_{timestamp}.db",
        media_type="application/octet-stream"
    )

@app.post("/api/data/clear/cache")
async def clear_cache():
    """清空消息去重缓存"""
    count = database.clear_reply_cache()
    return {"success": True, "message": f"已清空回复去重缓存 (共 {count} 条记录)！"}

@app.post("/api/data/reset")
async def reset_system():
    """一键重置系统数据库 (清空好友、日志、缓存并恢复初始配置)"""
    if bot_manager.is_running:
        await bot_manager.stop()
    database.reset_all_data()
    return {"success": True, "message": "系统数据库已成功恢复出厂设置！"}

@app.get("/api/system_logs")
async def get_system_logs():
    """获取最近实时运行控制台日志"""
    return list(system_logs_buffer)

@app.post("/api/system_logs/clear")
async def clear_system_logs():
    """清空实时运行控制台日志"""
    system_logs_buffer.clear()
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
