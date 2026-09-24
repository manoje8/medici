"""API routes for conversation session history.

Endpoints let the frontend list past sessions, load a specific
session's conversation turns, and delete sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request

if TYPE_CHECKING:
    from medici.agents.memory.conversation_store import ConversationStore


def _get_store(request: Request) -> ConversationStore:
    store = getattr(request.app.state, "conversation_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Conversation store not initialized")
    return store


def create_session_routes() -> APIRouter:
    router = APIRouter(prefix="/sessions", tags=["sessions"])

    @router.get("")
    async def list_sessions(
        user_id: str = Query(..., description="User ID to list sessions for"),
        limit: int = Query(30, ge=1, le=100),
        offset: int = Query(0, ge=0),
        store: ConversationStore = Depends(_get_store),
    ):
        """Return recent conversation sessions for a user, newest first."""
        sessions = await store.list_sessions(user_id=user_id, limit=limit, offset=offset)
        return {"sessions": sessions}

    @router.get("/{session_id}/history")
    async def get_session_history(
        session_id: str,
        store: ConversationStore = Depends(_get_store),
    ):
        """Return all conversation turns for a session."""
        turns = await store.get_session_history(session_id)
        return {"session_id": session_id, "turns": turns}

    @router.delete("/{session_id}")
    async def delete_session(
        session_id: str,
        store: ConversationStore = Depends(_get_store),
    ):
        """Delete a session and all its turns."""
        deleted = await store.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"deleted": True, "session_id": session_id}

    return router
