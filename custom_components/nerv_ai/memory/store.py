import logging

_LOGGER = logging.getLogger(__name__)

class MemoryStore:
    def __init__(self, db, db_lock):
        self._db, self._db_lock = db, db_lock

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
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS learned_facts_v3 (
                        chat_id TEXT NOT NULL,
                        category TEXT NOT NULL,
                        fact_text TEXT NOT NULL,
                        fact_key TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        UNIQUE(chat_id, fact_key)
                    )
                """)
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS action_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        domain TEXT NOT NULL,
                        service TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_action_log_entity_time 
                    ON action_log(entity_id, created_at)
                """)
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_config (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)
            await self._db.commit()

    # --- KRİTİK #2: Restart Sonrası Çift Bildirim Önleme (Flag Metotları) ---
    async def mark_notified(self, entity_id: str):
        await self.save_config(f"notified:{entity_id}", "1")

    async def clear_notified(self, entity_id: str):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("DELETE FROM system_config WHERE key = ?", (f"notified:{entity_id}",))
            await self._db.commit()

    async def is_notified(self, entity_id: str) -> bool:
        return await self.get_config(f"notified:{entity_id}") == "1"
    # ---------------------------------------------------------------------

    async def save_turn(self, chat_id: str, user_text: str, assistant_text: str):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)", (chat_id, "user", user_text))
                await cursor.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)", (chat_id, "assistant", assistant_text))
            await self._db.commit()

    async def save_fact(self, chat_id: str, category: str, fact_text: str, fact_key: str):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("""
                    INSERT OR REPLACE INTO learned_facts_v3 (chat_id, category, fact_text, fact_key) 
                    VALUES (?, ?, ?, ?)
                """, (chat_id, category, fact_text, fact_key))
            await self._db.commit()

    async def forget_fact(self, chat_id: str, fact_key: str):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("DELETE FROM learned_facts_v3 WHERE chat_id = ? AND fact_key = ?", (chat_id, fact_key))
            await self._db.commit()

    async def log_action(self, chat_id: str, entity_id: str, domain: str, service: str, status: str):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO action_log (chat_id, entity_id, domain, service, status) 
                    VALUES (?, ?, ?, ?, ?)
                """, (chat_id, entity_id, domain, service, status))
            await self._db.commit()

    async def cleanup_action_logs(self):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("DELETE FROM action_log WHERE created_at < datetime('now', '-30 days')")
            await self._db.commit()

    async def get_usage_report(self, chat_id: str) -> list[dict]:
        await self.cleanup_action_logs()
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("""
                    SELECT entity_id, domain, service, status, created_at 
                    FROM action_log 
                    WHERE chat_id = ? AND created_at >= datetime('now', '-7 days')
                    ORDER BY created_at DESC LIMIT 50
                """, (chat_id,))
                rows = await cursor.fetchall()
        
        return [{"entity_id": r[0], "domain": r[1], "service": r[2], "status": r[3], "created_at": r[4]} for r in rows]

    async def get_used_entities(self, chat_id: str) -> set:
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("SELECT DISTINCT entity_id FROM action_log WHERE chat_id = ?", (chat_id,))
                rows = await cursor.fetchall()
        return {r[0] for r in rows}

    async def save_config(self, key, value):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (key, value))
            await self._db.commit()

    async def get_config(self, key):
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
                row = await cursor.fetchone()
                return row[0] if row else None

    async def get_active_facts(self, chat_id: str) -> str:
        async with self._db_lock:
            async with self._db.cursor() as cursor:
                await cursor.execute("SELECT category, fact_text FROM learned_facts_v3 WHERE chat_id = ? AND is_active = 1", (chat_id,))
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