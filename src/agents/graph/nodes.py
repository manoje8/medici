import logfire

from src.agents.graph.state import State

_CHUNK_PREVIEW_MAX_CHARS = 300


def _build_structured_chunk_previews(chunks: list[dict]) -> str:
    """
    Build metadata-tagged raw chunk previews for the hop planner.

    Each chunk is truncated to ``_CHUNK_PREVIEW_MAX_CHARS`` and tagged
    with source/section metadata so the LLM can assess coverage without
    an expensive summarisation step.
    """
    if not chunks:
        return "(no chunks retrieved yet)"

    previews = []
    for i, c in enumerate(chunks):
        source = c.get("source", "unknown")
        section = c.get("section", "unknown")
        text = c.get("text", "")[:_CHUNK_PREVIEW_MAX_CHARS]
        score = c.get("score", "?")
        previews.append(
            f"[Chunk {i} | source={source} | section={section} | score={score}]\n{text}"
        )
    return "\n\n".join(previews)


# query Rewriter
async def rewrite_query(state: State, short_term, rewriter) -> dict:
    session = await short_term.get_session(state["session_id"])
    result = await rewriter.rewrite(state["original_message"], session)

    return {
        "current_query": result["rewritten_query"],
        "effective_query": result["rewritten_query"],
        "was_rewritten": result["was_rewritten"],
        "resolved_references": result["resolved_references"],
    }


# Router
async def route(state: State, router) -> dict:
    classification = await router.classify(
        state["effective_query"], conversation_history=state["retrieval_history"]
    )

    return {
        "question_category": classification["primary_category"],
        "classification": classification,
    }


# Planner
async def plan(state: State, planner) -> dict:
    sub_qs = await planner.decompose(state["effective_query"], state["question_category"])

    return {
        "hop_questions": sub_qs,
        "current_hop": 0,
        "retrieval_round": 0,
    }


# Retrieve & evaluate
async def retrieve(state: State, retrieval_agent) -> dict:
    current_query = state["current_query"]
    hop_questions = state.get("hop_questions", [])
    # Use the last hop question as the "original question" for reranking
    original_question = hop_questions[-1] if hop_questions else current_query

    round_result = await retrieval_agent.retrieve_and_evaluate(
        query=current_query,
        original_question=original_question,
        state=state,
        round_no=state["retrieval_round"],
    )

    return {
        "retrieval_history": state["retrieval_history"]
        + [
            {
                "query": round_result.query_used,
                "decision": round_result.decision.value,
                "reasoning": round_result.reasoning,
                "chunks": round_result.chunk_retrieved,
                "refined_query": getattr(round_result, "refined_query", None),
            }
        ],
        "retrieval_round": state["retrieval_round"] + 1,
        "total_retrieval_steps": state.get("total_retrieval_steps", 0) + 1,
    }


async def hop_check(state: State, planner) -> dict:
    """
    Assess retrieval sufficiency and decide the next action.

    After each retrieval round this node:
    1. Accumulates accepted chunks from the latest retrieval
    2. Builds structured raw-chunk previews of everything gathered so far
    3. Checks the hop budget
    4. Calls ``planner.plan_next_hop()`` to decide: rephrase / new_sub_question / sufficient
    5. Returns a state update with ``hop_decision`` for the edge router
    """

    last = state["retrieval_history"][-1]
    accepted = (state.get("accepted_chunks") or []) + (last.get("chunks") or [])
    current_hop = state.get("current_hop", 0)
    max_hops = state.get("max_hops", 4)
    hop_questions = list(state.get("hop_questions", []))

    # Budget check
    if current_hop >= max_hops:
        logfire.warning(
            "hop_budget_exhausted",
            current_hop=current_hop,
            max_hops=max_hops,
        )
        return {
            "accepted_chunks": accepted,
            "hop_decision": "exhausted",
        }

    context_preview = _build_structured_chunk_previews(accepted)

    hop_result = await planner.plan_next_hop(
        original_question=state.get("effective_query") or state.get("original_message", ""),
        hop_questions=hop_questions,
        retrieved_context=context_preview,
        question_category=state.get("question_category", "factual"),
    )

    next_action = hop_result.get("next_action", "sufficient")
    new_query = hop_result.get("query")
    reasoning = hop_result.get("reasoning", "")

    logfire.info(
        "hop_check_decision",
        next_action=next_action,
        current_hop=current_hop,
        max_hops=max_hops,
        num_accepted_chunks=len(accepted),
        reasoning=reasoning[:200] if reasoning else "",
    )

    update: dict = {
        "accepted_chunks": accepted,
    }

    if next_action in ("rephrase", "new_sub_question"):
        update["hop_decision"] = "retrieve_again"
        update["current_query"] = new_query
        update["current_hop"] = current_hop + 1
        update["retrieval_round"] = 0  # reset per-hop retrieval round counter
        if new_query:
            update["hop_questions"] = hop_questions + [new_query]
    else:
        # "sufficient" or any unrecognised value → proceed to grade
        update["hop_decision"] = "sufficient"

    return update


# Grader
async def grade(state: State, grader) -> dict:
    return await grader.grade(state)


# Synthesizer
async def synthesize(state: State, synthesizer) -> dict:
    answer = await synthesizer.synthesize(state)

    accepted_chunks = state.get("accepted_chunks") or []
    sources = list(set(c["source"] for c in accepted_chunks if c.get("source")))

    return {"final_answer": answer, "sources": sources}


async def direct_synthesize(state: State, synthesizer) -> dict:
    """Direct synthesis for simple queries (bypasses planning/grading loop)."""
    result = await synthesizer.direct_synthesize(state)

    return {
        "final_answer": result["final_answer"],
        "sources": result.get("sources", []),
    }


async def handle_simple_response(state: State, synthesizer) -> dict:
    """Handle chitchat/meta queries without retrieval."""
    result = await synthesizer.handle_simple_response(state)

    return {
        "final_answer": result["final_answer"],
        "sources": [],
    }


async def rewrite_for_refinement(state: State) -> dict:
    """
    Reset retrieval state for a grader-triggered re-retrieval pass.

    Called when route_after_grade decides the grader's needs_refinement flag
    warrants another full retrieval cycle.  Increments refinement_loops so the
    loop-guard in route_after_grade can enforce the ceiling, and resets all
    per-cycle counters so the graph re-runs the hop loop cleanly.

    Note: hop_questions is intentionally preserved — we re-retrieve for the
    same decomposed plan rather than re-running the planner.
    """
    return {
        "refinement_loops": state.get("refinement_loops", 0) + 1,
        "retrieval_round": 0,
        "current_hop": 0,
        "total_retrieval_steps": 0,
        "accepted_chunks": [],
        "retrieval_history": [],
        "hop_decision": "",
    }
