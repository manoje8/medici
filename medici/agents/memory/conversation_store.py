"""Durable PostgreSQL-backed conversation store.

Persists every session and turn so that conversation history survives
Redis TTL expiry and can be browsed / reloaded from the sidebar.
The existing :class:`ShortTermMemoryManager` (Redis) continues to serve
as the hot cache for in-flight sessions; this store is the durable
backend.
"""

from __future__ import annotations

import json
from datetime import datetime

import logfire


class ConversationStore:
    """CRUD operations on ``conversation_sessions`` / ``conversation_turns``."""

    def __init__(self, pool) -> None:
        self.pool = pool

    async def setup(self) -> None:
        """Create tables and indexes if they do not already exist."""
        create_sessions_sql = """
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                session_id  TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                title       TEXT NOT NULL DEFAULT 'New Chat',
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """
        create_turns_sql = """
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id          SERIAL PRIMARY KEY,
                session_id  TEXT NOT NULL
                             REFERENCES conversation_sessions(session_id)
                             ON DELETE CASCADE,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                metadata    JSONB DEFAULT '{}',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """
        idx_sessions_user = """
            CREATE INDEX IF NOT EXISTS idx_convsess_user
            ON conversation_sessions(user_id, updated_at DESC);
        """
        idx_turns_session = """
            CREATE INDEX IF NOT EXISTS idx_convturns_session
            ON conversation_turns(session_id, created_at);
        """

        async with self.pool.connection() as conn:
            await conn.execute(create_sessions_sql)
            await conn.execute(create_turns_sql)
            await conn.execute(idx_sessions_user)
            await conn.execute(idx_turns_session)

        logfire.info("Conversation store tables ready")

    @staticmethod
    def _generate_title(first_message: str, max_length: int = 48) -> str:
        """Derive a short title from the first user message."""
        title = first_message.strip().replace("\n", " ")
        if len(title) > max_length:
            title = title[:max_length].rsplit(" ", 1)[0] + "…"
        return title or "New Chat"

    async def save_session(
        self,
        session_id: str,
        user_id: str,
        title: str | None = None,
    ) -> None:
        """Insert or update a conversation session.

        On conflict (session already exists) only ``updated_at`` is
        refreshed. The title is set only on first insert.
        """
        upsert_sql = """
            INSERT INTO conversation_sessions
                (session_id, user_id, title, created_at, updated_at)
            VALUES
                (%(session_id)s, %(user_id)s, %(title)s, NOW(), NOW())
            ON CONFLICT (session_id) DO UPDATE
                SET updated_at = NOW()
        """
        try:
            async with self.pool.connection() as conn:
                await conn.execute(
                    upsert_sql,
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "title": title or "New Chat",
                    },
                )
        except Exception:
            logfire.warning(
                "conversation_store.save_session failed",
                session_id=session_id,
                exc_info=True,
            )

    async def update_title(self, session_id: str, title: str) -> None:
        """Update the title of an existing session."""
        sql = """
            UPDATE conversation_sessions
            SET title = %(title)s, updated_at = NOW()
            WHERE session_id = %(session_id)s
        """
        try:
            async with self.pool.connection() as conn:
                await conn.execute(sql, {"session_id": session_id, "title": title})
        except Exception:
            logfire.warning(
                "conversation_store.update_title failed",
                session_id=session_id,
                exc_info=True,
            )

    async def save_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """Append a single turn to the durable store."""
        insert_sql = """
            INSERT INTO conversation_turns
                (session_id, role, content, metadata, created_at)
            VALUES
                (%(session_id)s, %(role)s, %(content)s,
                 %(metadata)s, NOW())
        """
        touch_sql = """
            UPDATE conversation_sessions
            SET updated_at = NOW()
            WHERE session_id = %(session_id)s
        """
        try:
            async with self.pool.connection() as conn:
                await conn.execute(
                    insert_sql,
                    {
                        "session_id": session_id,
                        "role": role,
                        "content": content,
                        "metadata": json.dumps(metadata or {}),
                    },
                )
                await conn.execute(touch_sql, {"session_id": session_id})
        except Exception:
            logfire.warning(
                "conversation_store.save_turn failed",
                session_id=session_id,
                exc_info=True,
            )

    async def list_sessions(
        self,
        user_id: str,
        limit: int = 30,
        offset: int = 0,
    ) -> list[dict]:
        """Return recent sessions for a user, newest first.

        Each dict: ``{session_id, title, created_at, updated_at, preview}``.
        ``preview`` is the content of the first user turn (if any).
        """
        sql = """
            SELECT
                s.session_id,
                s.title,
                s.created_at,
                s.updated_at,
                (
                    SELECT content
                    FROM conversation_turns t
                    WHERE t.session_id = s.session_id
                      AND t.role = 'user'
                    ORDER BY t.created_at ASC
                    LIMIT 1
                ) AS preview
            FROM conversation_sessions s
            WHERE s.user_id = %(user_id)s
            ORDER BY s.updated_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        try:
            async with self.pool.connection() as conn:
                cursor = await conn.execute(
                    sql,
                    {"user_id": user_id, "limit": limit, "offset": offset},
                )
                rows = await cursor.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "session_id": row["session_id"],
                        "title": row["title"],
                        "created_at": row["created_at"].isoformat()
                        if isinstance(row["created_at"], datetime)
                        else str(row["created_at"]),
                        "updated_at": row["updated_at"].isoformat()
                        if isinstance(row["updated_at"], datetime)
                        else str(row["updated_at"]),
                        "preview": row.get("preview", ""),
                    }
                )
            return results

        except Exception:
            logfire.warning(
                "conversation_store.list_sessions failed",
                user_id=user_id,
                exc_info=True,
            )
            return []

    async def get_session_history(self, session_id: str) -> list[dict]:
        """Return all turns for a session, oldest first.

        Each dict: ``{role, content, created_at, metadata}``.
        """
        sql = """
            SELECT role, content, metadata, created_at
            FROM conversation_turns
            WHERE session_id = %(session_id)s
            ORDER BY created_at ASC
        """
        try:
            async with self.pool.connection() as conn:
                cursor = await conn.execute(sql, {"session_id": session_id})
                rows = await cursor.fetchall()

            results = []
            for row in rows:
                meta = row.get("metadata", {})
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        meta = {}
                results.append(
                    {
                        "role": row["role"],
                        "content": row["content"],
                        "created_at": row["created_at"].isoformat()
                        if isinstance(row["created_at"], datetime)
                        else str(row["created_at"]),
                        "metadata": meta,
                    }
                )
            return results

        except Exception:
            logfire.warning(
                "conversation_store.get_session_history failed",
                session_id=session_id,
                exc_info=True,
            )
            return []

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its turns (CASCADE)."""
        sql = """
            DELETE FROM conversation_sessions
            WHERE session_id = %(session_id)s
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(sql, {"session_id": session_id})
                return result.rowcount > 0
        except Exception:
            logfire.warning(
                "conversation_store.delete_session failed",
                session_id=session_id,
                exc_info=True,
            )
            return False
