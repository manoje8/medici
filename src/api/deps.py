from fastapi import HTTPException, Request

from src.agents.graph.runner import GraphPipeline
from src.ingestion.processor import Processor


def get_pipeline(request: Request) -> GraphPipeline:
    pipeline = request.app.state.pipeline
    if not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    return pipeline


def get_processor(request: Request) -> Processor:
    processor = request.app.state.processor
    if not processor:
        raise HTTPException(status_code=503, detail="Processor not initialized")
    return processor
