from typing import Any

from src.ingestion.chunking.chunk import Chunk
from src.ingestion.chunking.Chunker import Chunker


class SemanticChunker(Chunker):
    def __init__(self, **kwargs: Any) -> None:
        pass

    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        pass

    def chunk_multimodal_items(
        self,
        items: list[dict[str, Any]],
        doc_id: str,
        source_file: str,
        start_index: int,
        storage=None,
    ):
        pass
