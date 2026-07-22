from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.agents.graph.runner import GraphPipeline
from src.api.deps import get_pipeline


class QueryRequest(BaseModel):
    question: str
    user_id: str
    session_id: str | None = None
    is_multi_retriever: bool = False


def create_query_routes(api_key: str | None = None, top_k: int = 60):
    router = APIRouter(tags=["query"])

    @router.post("/query")
    async def create_query(
        body: QueryRequest,
        pipeline: GraphPipeline = Depends(get_pipeline),
        # _auth: dict = Depends(require_auth),
    ):
        result = await pipeline.chat(
            user_message=body.question,
            session_id=body.session_id,
            user_id=body.user_id,
        )
        return {
            "answer": result["answer"],
            "session_id": result["session_id"],
            "sources": result["sources"],
            "images": result.get("images", []),
            "query_was_rewritten": result["query_was_rewritten"],
            "cache_hit": result.get("cache_hit", False),
            "cache_similarity": result.get("cache_similarity"),
            "token_usage": result.get("token_usage", {}),
        }

    return router
