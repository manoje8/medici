"""
Embedding vector cache

Stores (text_hash -> vector) in a PostgreSQL table. Uses an asyncpg
connection pool for concurrent reads and writes; a single asyncio.Lock
serializes to write + LRU-eviction step so eviction stays consistent
under concurrent writers within this process. (Across multiple processes,
eviction races are possible; see note on advisory locks below if that
matters for your deployment.)

Cache key: SHA-256 of the stripped chunk text.
Eviction:  LRU -- oldest ``accessed_at`` rows are pruned when ``max_entries``
           is exceeded.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import asyncpg
import logfire

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS embeddings (
    key         TEXT PRIMARY KEY,
    vector_json TEXT NOT NULL,
    dimensions  INTEGER NOT NULL,
    accessed_at DOUBLE PRECISION NOT NULL DEFAULT extract(epoch FROM clock_timestamp())
);
CREATE INDEX IF NOT EXISTS idx_accessed ON embeddings(accessed_at);
"""


class EmbeddingCache:
    """Postgres-backed embedding vector cache with LRU eviction.

    Parameters
    ----------
    dsn:
        PostgreSQL connection string, e.g.
        ``postgresql://user:pass@host:5432/dbname``.
    max_entries:
        Maximum number of cached vectors before LRU eviction kicks in.
    pool_min_size / pool_max_size:
        Bounds for the underlying asyncpg connection pool.

    """

    def __init__(self, dsn: str, max_entries: int = 50_000) -> None:
        self.dsn = dsn
        self.max_entries = max_entries
        self._write_lock = asyncio.Lock()
        self._pool: asyncpg.Pool | None = None

    @classmethod
    async def create(
        cls,
        dsn: str,
        max_entries: int = 50_000,
        pool_min_size: int = 1,
        pool_max_size: int = 10,
    ) -> EmbeddingCache:
        """Create and initialize a cache backed by a live connection pool."""
        self = cls(dsn, max_entries=max_entries)
        self._pool = await asyncpg.create_pool(dsn, min_size=pool_min_size, max_size=pool_max_size)
        await self._ensure_db()
        return self

    async def get(self, text: str) -> list[float] | None:
        """Return cached vector for ``text``, or ``None`` on miss."""
        key = self._key(text)
        pool = self._require_pool()

        row = await pool.fetchrow("SELECT vector_json FROM embeddings WHERE key = $1", key)
        if row is None:
            return None

        # Touch access time (best-effort; don't fail on error)
        try:
            await pool.execute(
                "UPDATE embeddings SET accessed_at = extract(epoch FROM clock_timestamp()) "
                "WHERE key = $1",
                key,
            )
        except asyncpg.PostgresError:
            pass

        logfire.debug("EmbeddingCache HIT", key_prefix=key[:8])
        return json.loads(row["vector_json"])

    async def put(self, text: str, vector: list[float]) -> None:
        """Store ``vector`` for ``text``, evicting LRU entries if needed."""
        key = self._key(text)
        vector_json = json.dumps(vector)
        dims = len(vector)
        pool = self._require_pool()

        async with self._write_lock:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO embeddings (key, vector_json, dimensions, accessed_at)
                        VALUES ($1, $2, $3, extract(epoch FROM clock_timestamp()))
                        ON CONFLICT (key) DO UPDATE SET
                            vector_json = excluded.vector_json,
                            accessed_at = excluded.accessed_at
                        """,
                        key,
                        vector_json,
                        dims,
                    )

                    count = await conn.fetchval("SELECT COUNT(*) FROM embeddings")
                    if count > self.max_entries:
                        evict_count = count - self.max_entries
                        await conn.execute(
                            """
                            DELETE FROM embeddings
                            WHERE key IN (
                                SELECT key FROM embeddings
                                ORDER BY accessed_at ASC
                                LIMIT $1
                            )
                            """,
                            evict_count,
                        )
                        logfire.info(
                            "EmbeddingCache evicted LRU entries",
                            evicted=evict_count,
                            remaining=self.max_entries,
                        )

    async def stats(self) -> dict[str, Any]:
        """Return cache statistics (entries, DB size in MB)."""
        pool = self._require_pool()
        count = await pool.fetchval("SELECT COUNT(*) FROM embeddings")
        size_bytes = await pool.fetchval("SELECT pg_total_relation_size('embeddings')")
        return {
            "entries": count,
            "max_entries": self.max_entries,
            "size_mb": round((size_bytes or 0) / 1024 / 1024, 2),
            "dsn": self._redacted_dsn(),
        }

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.strip().encode()).hexdigest()

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError(
                "EmbeddingCache pool not initialised; use `await EmbeddingCache.create(...)` "
                "instead of the constructor."
            )
        return self._pool

    async def _ensure_db(self) -> None:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                for statement in _CREATE_SQL.strip().split(";"):
                    statement = statement.strip()
                    if statement:
                        await conn.execute(statement)
        logfire.info("EmbeddingCache initialised", dsn=self._redacted_dsn())

    def _redacted_dsn(self) -> str:
        # Avoid logging credentials embedded in the DSN.
        if "@" in self.dsn:
            scheme_and_creds, rest = self.dsn.split("@", 1)
            scheme = scheme_and_creds.split("://", 1)[0]
            return f"{scheme}://***@{rest}"
        return self.dsn
