import uuid

import logfire

from src.agents.memory.conversation_model import ConversationSession
from src.common.utils.config import config


class GraphPipeline:
    def __init__(self, graph, short_term_memory, semantic_cache=None, llm_clients=None):
        self.graph = graph
        self.short_term = short_term_memory
        self._semantic_cache = semantic_cache
        self._llm_clients: list = llm_clients or []

    async def chat(self, user_message: str, session_id: str, user_id: str) -> dict:

        result = {}

        if not session_id:
            logfire.info("Creating new session...")
            session_id = f"{user_id}_{uuid.uuid4()}"

        session: ConversationSession = await self.short_term.get_session(session_id)
        if not session:
            session = await self.short_term.create_session(user_id)

        await self.short_term.append_turn(
            session=session,
            role="user",
            content=user_message,
        )

        for client in self._llm_clients:
            client.reset_usage()

        if self._semantic_cache is not None:
            try:
                cached = await self._semantic_cache.lookup(user_message)
                if cached is not None:
                    logfire.info(
                        "SemanticCache served response",
                        similarity=cached.similarity,
                        session_id=session.session_id,
                    )
                    await self.short_term.append_turn(
                        session=session,
                        role="assistant",
                        content=cached.answer,
                        metadata={"sources": cached.sources},
                    )
                    return {
                        "answer": cached.answer,
                        "session_id": session.session_id,
                        "sources": cached.sources,
                        "query_was_rewritten": False,
                        "retrieval_rounds": 0,
                        "cache_hit": True,
                        "cache_similarity": round(cached.similarity, 4),
                        "token_usage": cached.token_usage,
                    }
            except Exception as e:
                # Cache errors must never break the hot path
                logfire.warning(f"SemanticCache lookup failed, running full pipeline: {e}")

        graph_config = {"configurable": {"thread_id": session.session_id}}

        history = session.to_prompt_format()

        initial_state = {
            "session_id": session.session_id,
            "user_id": user_id,
            "original_message": user_message,
            "effective_query": user_message,
            "was_rewritten": False,
            "conversational_history": history,
            "question_category": "",
            "hop_questions": [],
            "current_hop": 0,
            "max_hops": config.MAX_HOPS,
            "current_query": user_message,
            "retrieval_round": 0,
            "total_retrieval_steps": 0,
            "max_retrieval_rounds": config.MAX_RETRIEVAL_ROUND,
            "retrieval_history": [],
            "accepted_chunks": [],
            "hop_decision": "",
            "final_answer": "",
            "sources": [],
            "images": [],
            "doc_id_filter": None,
            "episodic_context": "",
        }

        try:
            result = await self.graph.ainvoke(initial_state, config=graph_config)
        except Exception as e:
            logfire.warning(f"Graph invocation Error: {str(e)}")
            return {
                "answer": "I apologize, but I encountered an error processing your request. Please try again.",
                "session_id": session.session_id,
                "sources": [],
                "query_was_rewritten": False,
                "retrieval_hops": 0,
                "cache_hit": False,
                "token_usage": {},
                "error": str(e),
            }

        token_usage = {}
        total_calls = 0
        total_tokens = 0
        for client in self._llm_clients:
            snap = client.usage_snapshot()
            token_usage[snap["model"]] = snap
            total_calls += snap["calls"]
            total_tokens += snap["total_tokens"]

        logfire.info(
            "pipeline_token_budget",
            total_calls=total_calls,
            total_tokens=total_tokens,
            breakdown=token_usage,
            session_id=session.session_id,
        )

        await self.short_term.append_turn(
            session=session,
            role="assistant",
            content=result["final_answer"],
            metadata={"sources": result.get("sources", [])},
        )

        if self._semantic_cache is not None:
            try:
                await self._semantic_cache.store(
                    query=user_message,
                    answer=result["final_answer"],
                    sources=result.get("sources", []),
                    token_usage={"total_calls": total_calls, "total_tokens": total_tokens},
                )
            except Exception as e:
                logfire.warning(f"SemanticCache store failed: {e}")

        return {
            "answer": result["final_answer"],
            "session_id": session.session_id,
            "sources": result["sources"],
            "images": result.get("images", []),
            "query_was_rewritten": result["was_rewritten"],
            "retrieval_hops": result.get("current_hop", 0),
            "cache_hit": False,
            "token_usage": token_usage,
        }
