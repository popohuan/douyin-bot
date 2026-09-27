import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, List, Dict

class MessageStorage:
    def __init__(self, db_path: str = "messages_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 记录已回复的消息哈希，防止重复回复
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS replied_cache (
                    msg_hash TEXT PRIMARY KEY,
                    friend_nickname TEXT,
                    msg_content TEXT,
                    reply_content TEXT,
                    created_at TIMESTAMP
                )
            """)
            # 记录历史对话存档，便于做上下文长期记忆
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    friend_nickname TEXT,
                    sender TEXT,  -- 'friend' or 'me'
                    content TEXT,
                    timestamp TEXT,
                    recorded_at TIMESTAMP
                )
            """)
            conn.commit()

    def _compute_hash(self, friend_nickname: str, content: str) -> str:
        """根据发送人、内容生成唯一指纹（可附加最近时间戳）"""
        raw = f"{friend_nickname}:{content.strip()}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def is_replied(self, friend_nickname: str, content: str) -> bool:
        """检查该好友发送的这条消息是否已经回复过"""
        msg_hash = self._compute_hash(friend_nickname, content)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM replied_cache WHERE msg_hash = ?", (msg_hash,))
            return cursor.fetchone() is not None

    def record_reply(self, friend_nickname: str, incoming_content: str, reply_content: str):
        """记录回复历史"""
        msg_hash = self._compute_hash(friend_nickname, incoming_content)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO replied_cache 
                (msg_hash, friend_nickname, msg_content, reply_content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (msg_hash, friend_nickname, incoming_content, reply_content, datetime.now()))
            
            # 同时存入对话流
            cursor.execute("""
                INSERT INTO conversation_logs (friend_nickname, sender, content, timestamp, recorded_at)
                VALUES (?, 'friend', ?, ?, ?)
            """, (friend_nickname, incoming_content, "", datetime.now()))
            
            cursor.execute("""
                INSERT INTO conversation_logs (friend_nickname, sender, content, timestamp, recorded_at)
                VALUES (?, 'me', ?, ?, ?)
            """, (friend_nickname, reply_content, "", datetime.now()))
            conn.commit()
