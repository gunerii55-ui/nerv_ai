"""SQLite Memory Store for NervAI."""
import logging
import asyncio
import aiosqlite
from typing import Dict, List, Any

_LOGGER = logging.getLogger(__name__)

class MemoryStore:
    def __init__(self, db: aiosqlite.Connection, db_lock: asyncio.Lock):
        self._db = db
        self._lock = db_lock

    async def async_init_db(self):
        """Tabloları ve indeksleri oluştur."""
        async with self._lock:
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS learned_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(chat_id, fact_key)
                )
            """)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS conversation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            await self._db.execute("CREATE INDEX IF NOT EXISTS idx_conv_chat_time ON conversation_log(chat_id, created_at)")
            await self._db.commit()

    async def save_fact(self, chat_id: str, key: str, value: str):
        """Kalıcı bir kural/bilgi kaydet (Upsert mantığı)."""
        async with self._lock:
            await self._db.execute("""
                INSERT INTO learned_facts (chat_id, fact_key, fact_value)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id, fact_key) DO UPDATE SET fact_value=excluded.fact_value
            """, (chat_id, key, value))
            await self._db.commit()

    async def save_turn(self, chat_id: str, user_text: str, assistant_reply: str):
        """Konuşma geçmişini kaydet."""
        async with self._lock:
            await self._db.execute("INSERT INTO conversation_log (chat_id, role, content) VALUES (?, 'user', ?)", (chat_id, user_text))
            await self._db.execute("INSERT INTO conversation_log (chat_id, role, content) VALUES (?, 'assistant', ?)", (chat_id, assistant_reply))
            await self._db.commit()

    async def build_context(self, chat_id: str, log_limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """Orkestratör için hafızayı paketle."""
        async with self._lock:
            # Gerçekleri çek
            facts_cursor = await self._db.execute("SELECT fact_key, fact_value FROM learned_facts WHERE chat_id = ?", (chat_id,))
            facts = [{"key": row[0], "value": row[1]} for row in await facts_cursor.fetchall()]

            # Son konuşmaları çek (Eskiden yeniye sıralı)
            log_cursor = await self._db.execute("""
                SELECT role, content FROM (
                    SELECT role, content, created_at FROM conversation_log 
                    WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?
                ) ORDER BY created_at ASC
            """, (chat_id, log_limit))
            recent_log = [{"role": row[0], "content": row[1]} for row in await log_cursor.fetchall()]

        return {"facts": facts, "recent_log": recent_log}