"""
Session-scoped registry for multi-user isolation.
Keeps non-serializable backend objects (vectorstores, agents, docling docs)
out of Reflex state.
"""
import uuid
from typing import Dict, Any


class SessionRegistry:
    """Lightweight in-memory registry keyed by session_id."""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self._store[session_id] = {}
        return session_id

    def get(self, session_id: str) -> Dict[str, Any]:
        return self._store.get(session_id, {})

    def set(self, session_id: str, key: str, value: Any):
        if session_id not in self._store:
            self._store[session_id] = {}
        self._store[session_id][key] = value

    def clear(self, session_id: str):
        if session_id in self._store:
            entry = self._store[session_id]
            vs = entry.get("vectorstore")
            if vs:
                try:
                    vs.delete_collection()
                except Exception:
                    pass
            self._store[session_id] = {}

    def delete(self, session_id: str):
        self.clear(session_id)
        if session_id in self._store:
            del self._store[session_id]


_registry = SessionRegistry()


def get_registry() -> SessionRegistry:
    return _registry
