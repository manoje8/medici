import asyncio
import hashlib
import json
import time
from pathlib import Path

import logfire
from tqdm import tqdm

from src.common.services.qdrant import QdrantStorageService
from src.common.services.sparse_index import SparseSearchIndex
from src.common.storage.storage_factory import StorageFactory
from src.common.utils.config import config
from src.common.utils.constants import (
    HTML_FORMATS,
    OFFICE_FORMATS,
    TEXT_FORMATS,
    ChunkerStrategy,
    ParseMethod,
    StorageType,
)
from src.common.utils.doc_cache import DocumentCache
from src.common.utils.helper import separate_content
from src.ingestion.chunking.chunk import BatchProcess
from src.ingestion.chunking.chunker_factory import create_chunker
from src.ingestion.chunking.chunking_config import ChunkingConfig
from src.ingestion.embedding import EmbeddingService
from src.ingestion.parser.docling_parser import DoclingParser
from src.ingestion.parser.google_doc_ai import GoogleDocAI


class Processor:
    def __init__(self, cache_dir: str | None = None, max_concurrency: int = 4):
        self.embedding_service = EmbeddingService(
            model_name=config.EMBEDDING_MODEL_NAME,
            dimensions=config.EMBEDDING_DIMENSIONS,
            batch_size=config.EMBEDDING_BATCH_SIZE,
        )
        self.storage_service = QdrantStorageService(
            url=config.QDRANT_CLUSTER_ENDPOINT,
            collection_name=config.QDRANT_COLLECTION_NAME,
            vector_size=self.embedding_service.vector_size,
        )

        self._cache = DocumentCache(
            cache_dir=(Path(cache_dir) if hasattr(config, "cache_dir") else config.CACHE_DIR)
        )

        self.sparse_index = SparseSearchIndex()

        local_config = {
            "type": StorageType.LOCAL.value,
            "base_dir": config.STORAGE_BASE_DIR,
        }

        # cloud_config = {
        #     "type": StorageType.GCS.value,
        #     "bucket": config.GCP_PROCESSED_BUCKET,
        # }

        self.in_storage = StorageFactory.create(local_config)
        self._max_concurrency = max_concurrency

    def _supported_extensions(self) -> list[str]:
        return list(HTML_FORMATS | OFFICE_FORMATS | TEXT_FORMATS | {".pdf"})

    def _filter_supported_files(self, file_paths: list[str], recursive: bool = False):
        supported_extensions = set(self._supported_extensions())
        supported_files = []

        for file_path in file_paths:
            path = Path(file_path)
            if path.is_dir():
                if recursive:
                    for inside_path in path.rglob("*"):
                        if (
                            inside_path.is_file()
                            and inside_path.suffix.lower() in supported_extensions
                        ):
                            supported_files.append(str(inside_path))
                else:
                    for inside_path in path.glob("*"):
                        if (
                            inside_path.is_file()
                            and inside_path.suffix.lower() in supported_extensions
                        ):
                            supported_files.append(str(inside_path))
            elif path.is_file():
                if path.suffix.lower() in supported_extensions:
                    supported_files.append(str(path))
                else:
                    logfire.warn(f"Unsupported file format : {file_path}")

            else:
                logfire.warn(f"Path doesn't exist: {path}")

        return supported_files

    def get_parser_method(self, parser_type: str):
        parser_name = parser_type.strip().lower()

        if parser_name == ParseMethod.GOOGLE_DOC_AI:
            return GoogleDocAI()
        elif parser_name == ParseMethod.DOCLING:
            return DoclingParser()
        else:
            raise ValueError(f"Unsupported Parser type: {parser_type}")

    def _select_chunking_strategy(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()

        if suffix in HTML_FORMATS | TEXT_FORMATS:
            return ChunkerStrategy.RECURSIVE_CHARACTER
        elif suffix in OFFICE_FORMATS or suffix == ".pdf":
            return ChunkerStrategy.RECURSIVE_CHARACTER
        else:
            return ChunkerStrategy.FIXED

    def _generate_cache_key(self, file_path: Path, parse_method: str) -> str:
        mtime = file_path.stat().st_mtime

        config_dict = {
            "file_path": str(file_path),
            "mtime": mtime,
            "parse_method": parse_method,
        }

        config_str = json.dumps(config_dict, sort_keys=True)
        cache_key = hashlib.md5(config_str.encode()).hexdigest()

        return cache_key

    def _get_cached_result(self, cache_key: str, file_path: Path, parse_method: str):
        return self._cache.get(cache_key)

    def _store_cache_result(
        self,
        cache_key: str,
        content_list: list[dict],
        file_path: Path,
        parser: str,
        parse_method: str = None,
    ):
        self._cache.store(
            cache_key, content_list, file_path, parse_method=parse_method, parser=parser
        )

    def _generate_doc_id(self, file_path: str | Path, read_bytes: int = 8192) -> str:
        path = Path(file_path).resolve()
        stat = path.stat()
        hasher = hashlib.sha256()
        hasher.update(str(stat.st_size).encode())

        with open(path, "rb") as f:
            hasher.update(f.read(read_bytes))

        return hasher.hexdigest()[:24]

    async def _chunk_doc_content(
        self,
        file_path: Path,
        content_list: str,
        doc_id: str,
        parse_method: ParseMethod,
        split_by_character: str | None = None,
    ):
        chunking_strategy = self._select_chunking_strategy(file_path)
        logfire.info(f"Starting chunking with strategy: {chunking_strategy} - {parse_method}")

        chunking_config = ChunkingConfig(type=chunking_strategy, size=512, overlap=64)

        chunker = create_chunker(chunking_config)
        chunks = chunker.chunk(content_list)

        logfire.info(
            f"Chunking complete: {len(chunks)} chunks produced from {len(content_list)} blocks"
        )

        # TODO: Update parent child chunking
        # enriched = chunking.build_parent_child_chunk(chunks)
        # logfire.info(f"Build parent child chunk: {len(enriched)}")

        return chunks

    async def process_document(
        self,
        file_path: str | Path,
        parse_method: ParseMethod,
        parser: str | None = None,
        display_stats: bool = False,
        split_by_character: str | None = None,
        split_by_character_only: str | None = None,
        doc_id: str | None = None,
        file_name: str | None = None,
        **kwargs,
    ):
        """
        Parse a single document. This is the sole per-file worker used both
        for one-off parsing and, via process_document_batch, for batches.
        """
        file_path = Path(file_path)
        logfire.info(f"Starting document parsing: {parse_method.value} - {file_path}")

        ext = file_path.suffix.lower()

        cache_key = self._generate_cache_key(file_path, parse_method.value)
        cache_result = self._get_cached_result(cache_key, file_path, parse_method.value)

        if cache_result is not None:
            logfire.info(f"Cache HIT - Returning cached result for {file_path}")
            doc_id = self._generate_doc_id(file_path)
            return cache_result, doc_id

        try:
            doc_parser = get_parser_method(parser_type=parse_method)

            if not doc_parser.check_installation():
                raise ImportError("Required package is not installed")

            if ext == ".pdf":
                logfire.info("Detected PDF file, parsing the pdf...")
                content_list = await asyncio.to_thread(
                    doc_parser.parse_pdf,
                    file_path=file_path,
                    method=parse_method.value,
                    **kwargs,
                )
            elif ext in HTML_FORMATS:
                logfire.info("Detected HTML file, parsing html...")
                content_list = await asyncio.to_thread(
                    doc_parser.parse_html,
                    file_path=file_path,
                    method=parse_method.value,
                    **kwargs,
                )
            elif ext in OFFICE_FORMATS:
                logfire.info("Detected office file, parsing document...")
                content_list = await asyncio.to_thread(
                    doc_parser.parse_doc,
                    file_path=file_path,
                    method=parse_method.value,
                    **kwargs,
                )
            elif ext in TEXT_FORMATS:
                logfire.info("Detected text file, parsing document...")
                content_list = await asyncio.to_thread(
                    doc_parser.parse_doc,
                    file_path=file_path,
                    method=parse_method.value,
                    **kwargs,
                )
            else:
                raise ValueError(
                    f"Unsupported file format: {ext}. "
                    f"Only supports PDF files, Office formats ({', '.join(OFFICE_FORMATS)}), "
                    f"HTML formats ({', '.join(HTML_FORMATS)}), "
                    f"and text formats ({', '.join(TEXT_FORMATS)})"
                )

        except Exception as e:
            logfire.error(f"Error during parsing: {str(e)}")
            raise

        msg = f"Parsing {file_path} completed! Extracted {len(content_list)} content block"
        logfire.info(msg)

        if len(content_list) == 0:
            raise ValueError("Parsing failed: No content extracted")

        self._store_cache_result(cache_key, content_list, file_path, parse_method.value, parser)

        doc_id = self._generate_doc_id(file_path)

        if display_stats:
            logfire.info("\n Content information: ")
            logfire.info(f"* Total content in list: {len(content_list)}")

            block_types: dict[str, int] = {}
            for block in content_list:
                if isinstance(block, dict):
                    block_type = block.get("type", "Unknown")
                    if isinstance(block_type, str):
                        block_types[block_type] = block_types.get(block_type, 0) + 1

            logfire.info("* Content block types: ")

            for block_type, count in block_types.items():
                logfire.info(f" - {block_type} : {count}")

        return content_list, doc_id

    async def _process_one_guarded(
        self,
        file_path: str,
        parse_method: ParseMethod,
        semaphore: asyncio.Semaphore,
        **kwargs,
    ):
        async with semaphore:
            try:
                content_list, doc_id = await self.process_document(
                    file_path=file_path, parse_method=parse_method, **kwargs
                )
                return file_path, True, content_list, doc_id, None
            except Exception as e:
                logfire.error(f"parser failed to process {file_path}: {str(e)}")
                return file_path, False, None, None, str(e)

    async def process_document_batch(
        self,
        file_paths: list[str],
        parse_method: ParseMethod,
        recursive: bool = False,
        show_progress: bool = True,
        output_dir: str | None = None,
        **kwargs,
    ) -> tuple[BatchProcess, dict[str, tuple[list, str]]]:
        """
        Parse many files concurrently using process_document as the single
        worker (no separate pass/fail-only parse, no double parsing).

        Returns (BatchProcess summary, {file_path: (content_list, doc_id)}
        for successful files).
        """
        start_time = time.time()
        supported_files = self._filter_supported_files(file_paths, recursive)

        if not supported_files:
            return (
                BatchProcess(
                    successful_files=[],
                    failed_files=[],
                    total_files=0,
                    processing_time=0.0,
                    errors={},
                    output_dir=output_dir,
                ),
                {},
            )

        logfire.info(f"Found {len(supported_files)} file to process")

        semaphore = asyncio.Semaphore(self._max_concurrency)
        tasks = [
            self._process_one_guarded(fp, parse_method, semaphore, **kwargs)
            for fp in supported_files
        ]

        pbar = (
            tqdm(total=len(supported_files), desc=f"processing files {parse_method}", unit="file")
            if show_progress
            else None
        )

        success_files, failed_files, errors, results = [], [], {}, {}
        try:
            for coro in asyncio.as_completed(tasks):
                file_path, ok, content_list, doc_id, error_msg = await coro
                if ok:
                    success_files.append(file_path)
                    results[file_path] = (content_list, doc_id)
                else:
                    failed_files.append(file_path)
                    errors[file_path] = error_msg
                if pbar:
                    pbar.update(1)
        finally:
            if pbar:
                pbar.close()

        processing_time = time.time() - start_time

        output = BatchProcess(
            successful_files=success_files,
            failed_files=failed_files,
            total_files=len(supported_files),
            processing_time=processing_time,
            errors=errors,
            output_dir=output_dir,
        )
        logfire.info(output.summary())

        return output, results

    async def ingest_document(
        self,
        file_path: str,
        parse_method: ParseMethod = ParseMethod.DOCLING,
        doc_id: str | None = None,
        split_by_character: str = "\n\n",
    ):
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content_list, doc_id = await self.process_document(
            file_path=file_path,
            doc_id=doc_id,
            split_by_character=split_by_character,
            parse_method=parse_method,
        )
        logfire.info(f"Stage 1 complete: {len(content_list)} content list")

        if parse_method == ParseMethod.DOCLING:
            content_list, multimodal_items = separate_content(content_list)

        return await self._chunk_embed_store(file_path, content_list, doc_id, parse_method)

    async def ingest_documents(
        self,
        file_paths: list[str],
        parse_method: ParseMethod,
        recursive: bool = False,
    ) -> dict:
        """
        Batch version of ingest_document: parses all files concurrently via
        process_document_batch, then chunks/embeds/stores each successfully
        parsed document.
        """

        batch_result, parsed = await self.process_document_batch(
            file_paths=file_paths, parse_method=parse_method, recursive=recursive
        )
        logfire.info(batch_result.summary())

        results = {}
        for file_path, (content_list, doc_id) in parsed.items():
            path = Path(file_path)
            if parse_method == ParseMethod.DOCLING:
                content_list, multimodal_items = separate_content(content_list)
            try:
                results[file_path] = await self._chunk_embed_store(
                    path, content_list, doc_id, parse_method
                )
            except Exception as e:
                logfire.error(f"Failed to chunk/embed/store {file_path}: {str(e)}")
                batch_result.failed_files.append(file_path)
                batch_result.errors[file_path] = str(e)

        return {"batch": batch_result, "results": results}

    async def _chunk_embed_store(
        self, file_path: Path, content_list, doc_id: str, parse_method: ParseMethod
    ) -> dict:
        chunks = await self._chunk_doc_content(
            file_path=file_path,
            content_list=content_list,
            doc_id=doc_id,
            parse_method=parse_method,
        )
        self.in_storage.upload(key="chunks", data=chunks)
        logfire.info(f"Document chunking completed: {len(chunks)}")

        embedded_chunks = await self.embedding_service.embed_chunks(chunks)
        self.in_storage.upload(key="embedded_chunks", data=embedded_chunks)
        logfire.info(f"Stage 3 complete: {len(embedded_chunks)} vectors")

        await self.storage_service.upsert_embedded_chunks(embedded_chunks)
        logfire.info("Stage 4 complete: stored in Qdrant")

        return {
            "doc_id": doc_id,
            "chunks_produced": len(chunks),
            "vectors_stored": len(embedded_chunks),
        }


def get_parser_method(parser_type: str):
    parser_name = parser_type.strip().lower()

    if parser_name == ParseMethod.GOOGLE_DOC_AI:
        return GoogleDocAI()
    elif parser_name == ParseMethod.DOCLING:
        return DoclingParser()
    else:
        raise ValueError(f"Unsupported Parser type: {parser_type}")
