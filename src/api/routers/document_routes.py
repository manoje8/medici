import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from src.api.config_api import config_api
from src.api.constants_api import ALLOWED_CONTENT_TYPES
from src.common.utils.constants import ParseMethod
from src.common.utils.helper import supported_extensions_list
from src.common.utils.tokenizer import TikTokenTokenizer
from src.ingestion.processor import Processor

INGESTION_ROOT = Path(config_api.INGESTION_ROOT).resolve()
INGESTION_ROOT.mkdir(parents=True, exist_ok=True)


class IngestionRequest(BaseModel):
    path: str | Path
    parse_method: ParseMethod
    doc_id: str | None = None


def create_document_routes():
    router = APIRouter(tags=["document"])

    tokenizer = TikTokenTokenizer()
    processor = Processor(tokenizer)

    @router.post("/ingestion")
    async def ingestion(
        file: UploadFile = File(...),
        parse_method: ParseMethod = Form(...),
        doc_id: str | None = Form(None),
    ):
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported content type: {file.content_type}",
            )

        original_name = Path(file.filename or "upload")
        ext = original_name.suffix.lower()
        if ext not in supported_extensions_list():
            raise HTTPException(status_code=400, detail="Unsupported file extension")

        safe_id = uuid.uuid4().hex
        user_dir = INGESTION_ROOT
        user_dir.mkdir(parents=True, exist_ok=True)
        dest_path = user_dir / f"{safe_id}{ext}"

        size = 0
        with dest_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > config_api.MAX_UPLOAD_BYTES:
                    out.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File too large",
                    )
                out.write(chunk)

        return await processor.ingest_document(
            file_path=dest_path,
            doc_id=doc_id,
            parse_method=parse_method,
        )

    @router.post("/bulk-ingestion")
    async def bulk_ingestion(body: IngestionRequest):
        return await processor.ingest_documents(
            file_paths=[body.path], parse_method=body.parse_method
        )

    return router
