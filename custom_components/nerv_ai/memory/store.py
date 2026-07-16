import json
import logging

_LOGGER = logging.getLogger(__name__)

class MemoryStore:
    def __init__(self, db, db_lock):
        self._db = db
        self._db_lock = db_lock

    async def async_init_db(self):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Tablo versiyonlandı (v2). Eski çakışma atlatıldı.
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS learned_facts_v2 (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT NOT NULL,
                        category TEXT NOT NULL,
                        fact_text TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            await self._db.commit()

    async def save_turn(self, chat_id: str, user_text: str, assistant_text: str):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)", (chat_id, "user", user_text))
                await cursor.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)", (chat_id, "assistant", assistant_text))
            await self._db.commit()

    async def save_fact(self, chat_id: str, category: str, fact_text: str):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("INSERT INTO learned_facts_v2 (chat_id, category, fact_text) VALUES (?, ?, ?)", (chat_id, category, fact_text))
            await self._db.commit()

    async def get_active_facts(self, chat_id: str) -> str:
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("SELECT category, fact_text FROM learned_facts_v2 WHERE chat_id = ? AND is_active = 1", (chat_id,))
                rows = await cursor.fetchall()
        
        if not rows:
            return ""
        
        facts_str = "Kullanıcı Tercihleri ve Rutinleri:\n"
        for row in rows:
            facts_str += f"- [{row[0].upper()}] {row[1]}\n"
        return facts_str

    async def build_context(self, chat_id: str, limit: int = 10) -> dict:
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("SELECT role, content FROM chat_history WHERE chat_id = ? ORDER BY id DESC LIMIT ?", (chat_id, limit))
                rows = await cursor.fetchall()
        
        recent_log = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
        facts = await self.get_active_facts(chat_id)
        
        return {"recent_log": recent_log, "facts": facts}