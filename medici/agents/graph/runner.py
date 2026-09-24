import traceback
import uuid

import logfire

from medici.agents.memory.conversation_model import ConversationSession
from medici.common.llm.fallback import STREAM_BREAK_SENTINEL, MidStreamFallbackError
from medici.common.utils.config import config

_UNCACHEABLE_CATEGORIES = frozenset({"chitchat", "meta", "conversational", "summarization"})


class GraphPipeline:
    def __init__(
        self,
        graph,
        short_term_memory,
        semantic_cache=None,
        llm_clients=None,
        conversation_store=None,
    ):
        self.graph = graph
        self.short_term = short_term_memory
        self._semantic_cache = semantic_cache
        self._llm_clients: list = llm_clients or []
        self._conversation_store = conversation_store

    async def _init_session(
        self, session_id: str, user_id: str, user_message: str
    ) -> tuple[ConversationSession, list[dict]]:
        """Resolve (or create) a session, record the user turn, and reset
        all LLM client usage counters.

        Returns ``(session, history)``."""
        is_new = False
        if not session_id:
            logfire.info("Creating new session...")
            session_id = f"{user_id}_{uuid.uuid4()}"

        session: ConversationSession = await self.short_term.get_session(session_id)
        if not session:
            session = await self.short_term.create_session(user_id, session_id=session_id)
            is_new = True

        history = session.to_history_dicts()

        await self.short_term.append_turn(
            session=session,
            role="user",
            content=user_message,
        )
        if self._conversation_store is not None:
            if is_new:
                from medici.agents.memory.conversation_store import ConversationStore

                title = ConversationStore._generate_title(user_message)
                await self._conversation_store.save_session(
                    session_id=session.session_id,
                    user_id=user_id,
                    title=title,
                )
            await self._conversation_store.save_turn(
                session_id=session.session_id,
                role="user",
                content=user_message,
            )

        for client in self._llm_clients:
            client.reset_usage()

        return session, history

    async def _check_cache(self, user_message: str, session: ConversationSession) -> dict | None:
        """Attempt a semantic-cache lookup.

        On a hit, appends the assistant turn and returns a response dict
        that both ``chat()`` and ``chat_stream()`` can use directly.
        Returns ``None`` on miss or when caching is disabled."""
        if self._semantic_cache is None:
            return None

        try:
            cached = await self._semantic_cache.lookup(user_message)
            if cached is None:
                return None

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
            logfire.warning(f"SemanticCache lookup failed, running full pipeline: {e}")
            return None

    def _build_initial_state(
        self,
        session: ConversationSession,
        user_id: str,
        user_message: str,
        history: list[dict],
    ) -> dict:
        """Build the graph initial-state dict."""
        return {
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

    def _collect_usage(
        self, session_id: str, *, label: str = "pipeline_token_budget"
    ) -> tuple[dict, int, int]:
        """
        Aggregate token-usage snapshots from all LLM clients.

        Returns ``(token_usage_by_model, total_calls, total_tokens)``.
        """
        token_usage: dict = {}
        total_calls = 0
        total_tokens = 0
        for client in self._llm_clients:
            snap = client.usage_snapshot()
            token_usage[snap["model"]] = snap
            total_calls += snap["calls"]
            total_tokens += snap["total_tokens"]

        logfire.info(
            label,
            total_calls=total_calls,
            total_tokens=total_tokens,
            breakdown=token_usage,
            session_id=session_id,
        )
        return token_usage, total_calls, total_tokens

    async def _maybe_store_cache(
        self,
        user_message: str,
        answer: str,
        sources: list,
        category: str,
        total_calls: int,
        total_tokens: int,
    ) -> None:
        """Store the response in the semantic cache if caching is enabled
        and the question category is cacheable."""
        if self._semantic_cache is None or not answer:
            return

        if category in _UNCACHEABLE_CATEGORIES:
            logfire.info(
                "SemanticCache store skipped (uncacheable category)",
                category=category,
            )
            return

        try:
            await self._semantic_cache.store(
                query=user_message,
                answer=answer,
                sources=sources,
                token_usage={"total_calls": total_calls, "total_tokens": total_tokens},
            )
        except Exception as e:
            logfire.warning(f"SemanticCache store failed: {e}")

    async def _save_assistant_turn(
        self,
        session: ConversationSession,
        answer: str,
        sources: list,
    ) -> None:
        """Append the assistant reply to short-term memory."""
        if answer:
            await self.short_term.append_turn(
                session=session,
                role="assistant",
                content=answer,
                metadata={"sources": sources},
            )
            if self._conversation_store is not None:
                await self._conversation_store.save_turn(
                    session_id=session.session_id,
                    role="assistant",
                    content=answer,
                    metadata={"sources": sources},
                )

    async def chat(self, user_message: str, session_id: str, user_id: str) -> dict:

        session, history = await self._init_session(session_id, user_id, user_message)

        # semantic cache fast-path
        cached_response = await self._check_cache(user_message, session)
        if cached_response is not None:
            return cached_response

        # graph execution
        graph_config = {"configurable": {"thread_id": session.session_id}}
        initial_state = self._build_initial_state(session, user_id, user_message, history)

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

        # post-processing
        token_usage, total_calls, total_tokens = self._collect_usage(
            session.session_id, label="pipeline_token_budget"
        )

        await self._save_assistant_turn(session, result["final_answer"], result.get("sources", []))

        await self._maybe_store_cache(
            user_message=user_message,
            answer=result["final_answer"],
            sources=result.get("sources", []),
            category=result.get("question_category", "").lower(),
            total_calls=total_calls,
            total_tokens=total_tokens,
        )

        return {
            "answer": result["final_answer"],
            "session_id": session.session_id,
            "sources": result["sources"],
            "images": result.get("images", []),
            "query_was_rewritten": result["was_rewritten"],
            "retrieval_hops": result.get("current_hop", 0),
            "cache_hit": False,
            "token_usage": token_usage,
            "faithfulness": {
                "score": result.get("faithfulness_score"),
                "passed": result.get("faithfulness_passed"),
                "skipped": result.get("faithfulness_skipped"),
            },
        }

    async def chat_stream(self, user_message: str, session_id: str, user_id: str):
        """
        Async-generator that streams pipeline progress + answer tokens.

        Yields dicts shaped for SSE consumption:

        ``{"type": "progress", "node": "<node_name>", "message": "..."}``
            Emitted as each LangGraph node completes, giving the frontend
            real-time stage visibility (routing, retrieval, grading …).

        ``{"type": "token", "content": "<text>"}``
            Emitted token-by-token during synthesis via
            ``SynthesizerAgent.stream_synthesize()``.

        ``{"type": "done", "session_id": "...", "sources": [...], ...}``
            Final event carrying session metadata and token-usage stats.

        ``{"type": "error", "message": "..."}``
            Emitted on unrecoverable errors; the stream then ends.

        Strategy
        --------
        1. Run the **full graph** (minus the synthesize node) via
           ``graph.ainvoke()`` so retrieval, grading, and all routing
           logic runs to completion.  Graph-level progress events are
           surfaced via ``graph.astream_events()``.
        2. Once the pre-synthesis state is ready, call
           ``synthesizer.stream_synthesize()`` directly so answer tokens
           are pushed to the client the moment they arrive from the LLM.
        3. Semantic cache hit-path returns immediately as a single
           ``done`` event (no tokens to stream).
        """

        session, history = await self._init_session(session_id, user_id, user_message)

        # semantic cache fast-path
        cached_response = await self._check_cache(user_message, session)
        if cached_response is not None:
            yield {"type": "done", **cached_response}
            return

        # graph execution (streaming)
        _NODE_LABELS: dict[str, str] = {
            "rewrite_query": "Rewriting query",
            "route": "Classifying question",
            "plan": "Planning retrieval",
            "retrieve": "Retrieving documents",
            "hop_check": "Evaluating retrieved context",
            "grade": "Grading relevance",
            "rewrite_for_refinement": "Refining query",
            "direct_synthesize": "Synthesizing answer",
            "handle_simple_response": "Generating response",
            "synthesize": "Synthesizing answer",
        }

        graph_config = {"configurable": {"thread_id": session.session_id}}
        initial_state = self._build_initial_state(session, user_id, user_message, history)

        final_state: dict = {}
        try:
            async for event in self.graph.astream_events(
                initial_state, config=graph_config, version="v2"
            ):
                kind = event.get("event")
                name = event.get("name", "")

                if kind == "on_chain_end" and name in _NODE_LABELS:
                    label = _NODE_LABELS[name]
                    yield {"type": "progress", "node": name, "message": label}

                    if name in ("synthesize", "direct_synthesize", "handle_simple_response"):
                        node_output = event.get("data", {}).get("output", {})
                        if isinstance(node_output, dict):
                            final_state.update(node_output)

        except Exception as exc:
            logfire.warning(f"Graph stream error: {exc}")
            logfire.warning(f"Full traceback: {traceback.format_exc()}")
            yield {"type": "error", "message": str(exc)}
            return

        if not final_state:
            try:
                final_state = await self.graph.ainvoke(initial_state, config=graph_config)
            except Exception as exc:
                logfire.warning(f"Graph ainvoke fallback error: {exc}")
                yield {"type": "error", "message": str(exc)}
                return

        answer = final_state.get("final_answer", "")
        sources = final_state.get("sources", [])
        images = final_state.get("images", [])
        was_rewritten = final_state.get("was_rewritten", False)

        if not answer and final_state.get("accepted_chunks"):
            # synthesizer = self.graph.nodes.get("synthesize")
            _synthesizer_agent = None
            try:
                _node_fn = self.graph.nodes["synthesize"].func  # type: ignore[attr-defined]
                _synthesizer_agent = _node_fn.keywords.get("synthesizer")
            except (AttributeError, KeyError):
                pass

            if _synthesizer_agent is not None:
                collected_tokens: list[str] = []
                try:
                    async for token in _synthesizer_agent.stream_synthesize(final_state):
                        # Filter out the stream-break sentinel so it never
                        # ends up in the assembled answer text.
                        if token == STREAM_BREAK_SENTINEL:
                            continue
                        collected_tokens.append(token)
                        yield {"type": "token", "content": token}
                    answer = "".join(collected_tokens)
                except MidStreamFallbackError as exc:
                    logfire.error(f"Mid-stream LLM fallback aborted for stage synthesis: {exc}")
                    # Emit a stream_break event so the frontend can show an
                    # appropriate "response interrupted" notice to the user.
                    yield {
                        "type": "stream_break",
                        "message": (
                            "The response was interrupted because the language "
                            "model failed mid-stream. Please retry your query."
                        ),
                        "tokens_before_break": len(collected_tokens),
                    }
                    # Use whatever partial tokens we collected, or fall back
                    # to the graph's stored final_answer.
                    partial = "".join(collected_tokens)
                    answer = partial if partial else final_state.get("final_answer", "")
                except Exception as exc:
                    logfire.warning(f"Streaming synthesis error: {exc}")
                    if not answer:
                        answer = final_state.get("final_answer", "")
            else:
                answer = final_state.get("final_answer", "")

        # post-processing (shared helpers)
        await self._save_assistant_turn(session, answer, sources)

        token_usage, total_calls, total_tokens = self._collect_usage(
            session.session_id, label="pipeline_stream_token_budget"
        )

        await self._maybe_store_cache(
            user_message=user_message,
            answer=answer,
            sources=sources,
            category=final_state.get("question_category", "").lower(),
            total_calls=total_calls,
            total_tokens=total_tokens,
        )

        yield {
            "type": "done",
            "answer": answer,
            "session_id": session.session_id,
            "sources": sources,
            "images": images,
            "query_was_rewritten": was_rewritten,
            "cache_hit": False,
            "token_usage": token_usage,
            "faithfulness": {
                "score": final_state.get("faithfulness_score"),
                "passed": final_state.get("faithfulness_passed"),
                "skipped": final_state.get("faithfulness_skipped"),
            },
        }
