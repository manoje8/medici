import asyncio
from dataclasses import dataclass

import logfire
from google import genai
from qdrant_client.http.models import PointStruct

from src.common.cache.embedding_cache import EmbeddingCache
from src.common.utils.config import config
from src.ingestion.chunking.chunk import Chunk


@dataclass
class EmbeddedChunk:
    chunk: Chunk
    vector: list[float]
    model_name: str

    def to_qdrant_point(self, point_id: str) -> PointStruct:
        payload = self.chunk.to_quant_payload()
        payload["embedding_model"] = self.model_name

        return PointStruct(id=point_id, vector=self.vector, payload=payload)


class EmbeddingService:
    def __init__(
        self,
        model_name: str = "text-embedding-004",
        dimensions: int = 768,
        batch_size: int = 100,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        cache: EmbeddingCache | None = None,
    ):
        self.client = genai.Client(
            vertexai=True, project=config.PROJECT_ID, location=config.LOCATION
        )
        self.model_name = model_name
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._cache = cache

    @property
    def vector_size(self) -> int:
        return self.dimensions or config.VECTOR_SIZE

    async def embed_single(self, text: str) -> list[float]:
        """Embed one piece of text, returning a cached vector when available."""

        text = text.strip()

        if not text:
            raise ValueError("Cannot embed empty text")

        if self._cache is not None:
            cached = await self._cache.get(text)
            if cached is not None:
                return cached

        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(
                    self.client.models.embed_content,
                    model=self.model_name,
                    contents=text,
                    config=genai.types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY",
                        output_dimensionality=self.dimensions,
                    ),
                )

                vector = response.embeddings[0].values
                if self._cache is not None:
                    await self._cache.set(text, vector)
                return vector
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logfire.error(
                        "Embedding failed after {max_retries} attempts",
                        max_retries=self.max_retries,
                        error=str(e),
                        text_length=len(text),
                    )
                    raise
                logfire.warning(
                    "Embedding attempt {attempt} failed, retrying...",
                    attempt=attempt + 1,
                    error=str(e),
                    text_length=len(text),
                )
                await asyncio.sleep(self.retry_delay * (attempt + 1))

    async def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        """Embed a list of chunks in batches, skipping API calls for cached chunks."""

        if not chunks:
            logfire.debug("No chunks to embed")
            return []

        result_map: dict[int, EmbeddedChunk] = {}
        uncached_indices: list[int] = []

        if self._cache is not None:
            for idx, chunk in enumerate(chunks):
                cached_vec = await self._cache.get(chunk.text)
                if cached_vec is not None:
                    result_map[idx] = EmbeddedChunk(
                        chunk=chunk, vector=cached_vec, model_name=self.model_name
                    )
                else:
                    uncached_indices.append(idx)
        else:
            uncached_indices = list(range(len(chunks)))

        cache_hits = len(result_map)
        if cache_hits:
            logfire.info(
                "Cache hit ratio: {hits}/{total} ({ratio:.1%})",
                hits=cache_hits,
                total=len(chunks),
                ratio=cache_hits / len(chunks),
            )

        uncached_chunks = [chunks[i] for i in uncached_indices]

        if uncached_chunks:
            total_batches = (len(uncached_chunks) + self.batch_size - 1) // self.batch_size

            embedded_uncached: list[EmbeddedChunk] = []
            for batch_num in range(total_batches):
                start = batch_num * self.batch_size
                end = start + self.batch_size
                batch = uncached_chunks[start:end]

                logfire.debug(
                    "Embedding batch {batch_num}/{total_batches} ({batch_size} chunks)",
                    batch_num=batch_num + 1,
                    total_batches=total_batches,
                    batch_size=len(batch),
                )

                for attempt in range(self.max_retries):
                    try:
                        batch_texts = [chunk.text for chunk in batch]
                        response = await asyncio.to_thread(
                            self.client.models.embed_content,
                            model=self.model_name,
                            contents=batch_texts,
                            config=genai.types.EmbedContentConfig(
                                task_type="RETRIEVAL_DOCUMENT",
                                output_dimensionality=self.dimensions,
                            ),
                        )

                        for chunk, emb in zip(batch, response.embeddings, strict=False):
                            ec = EmbeddedChunk(
                                chunk=chunk,
                                vector=emb.values,
                                model_name=self.model_name,
                            )
                            embedded_uncached.append(ec)
                            if self._cache is not None:
                                await self._cache.set(chunk.text, emb.values)
                        break

                    except Exception as e:
                        if attempt == self.max_retries - 1:
                            logfire.error(
                                "Batch {batch_num} failed after {max_retries} attempts",
                                batch_num=batch_num + 1,
                                max_retries=self.max_retries,
                                error=str(e),
                                batch_size=len(batch),
                            )
                            raise

                        logfire.warning(
                            "Batch {batch_num} attempt {attempt} failed, retrying...",
                            batch_num=batch_num + 1,
                            attempt=attempt + 1,
                            error=str(e),
                        )
                        await asyncio.sleep(self.retry_delay * (attempt + 1))

            for orig_idx, ec in zip(uncached_indices, embedded_uncached, strict=False):
                result_map[orig_idx] = ec

        embedded = [result_map[i] for i in range(len(chunks))]
        logfire.info(
            "Embedding complete: {total} vectors, {unique} unique from cache",
            total=len(embedded),
            unique=len(embedded) - cache_hits,
        )
        return embedded
