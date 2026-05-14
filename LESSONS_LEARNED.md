# Lessons Learned: Rebuilding the Reflex RAG App

## Overview
The original Reflex-based RAG app was a direct port of a working Streamlit application. Despite copying the same business logic, it failed catastrophically. This document explains **every failure mode**, **why it happened**, and the **rule to prevent it** in future Reflex projects.

---

## 1. Non-Serializable Objects in Reflex State

### What Went Wrong
The original `ProcessState` stored Docling `Document` objects (which contain PIL images, complex nested classes, and C++ bindings) directly in a state variable:
```python
class ProcessState(rx.State):
    docling_docs: List[Dict[str, Any]] = []  # Dicts contained actual Docling Document objects
```
Reflex serializes all state to JSON for the frontend. Docling `Document` objects are not JSON-serializable. The backend crashed with `TypeError` or `PicklingError` every time state synced.

### Why Streamlit Got Away With It
Streamlit's `st.session_state` is a plain Python dictionary with no serialization constraints. You can store anything.

### The Fix
Keep all non-serializable objects (Docling docs, Chroma vectorstores, LangGraph agents, PIL images) in a **pure Python session registry** (`core/session_registry.py`). Only pass **pre-serialized plain dicts/lists** into Reflex state.

### Rule
> **Never store custom class instances, database connections, or image objects inside `rx.State`. Only `str`, `int`, `float`, `bool`, `list`, `dict`, and `None`.**

---

## 2. Private Variables (`_leading_underscore`) Across Background Tasks

### What Went Wrong
The original upload handler stored file bytes in a "private" variable to pass them to a background task:
```python
class ProcessState(rx.State):
    _uploaded_data: List[Tuple[str, bytes]] = []

    async def handle_upload(self, files: List[rx.UploadFile]):
        self._uploaded_data = uploaded_data  # Set in normal event

    @rx.event(background=True)
    async def start_vectorization(self):
        await vector_store.process_documents(self._uploaded_data)  # Empty here!
```
Reflex strips or ignores private variables when crossing the boundary into `@rx.event(background=True)`. The background task saw an empty list, so processing silently did nothing.

### The Fix
Use a **module-level dictionary** keyed by `session_id` to hold bytes:
```python
_upload_buffers: Dict[str, List[Tuple[str, bytes]]] = {}
```
The normal event writes to it; the background task reads from it. This keeps bytes completely outside Reflex's state serialization pipeline.

### Rule
> **Do not use `_private_vars` to pass data between normal events and background tasks. Use public state vars (for serializable data) or module-level/session-scoped stores (for large/binary data).**

---

## 3. Bitwise Operators in Component Props

### What Went Wrong
The UI used Python bitwise operators for boolean logic inside component props:
```python
disabled=~ProcessState.selected_files.length()
disabled=ProcessState.uploaded_files & ~ProcessState.processed_files.length()
```
Python bitwise `~` on a list length (an `int`) works, but bitwise `&` between a **list** and an **int** raises `TypeError: unsupported operand type(s) for &: 'list' and 'int'`. Additionally, Reflex transpiles these props to JavaScript; bitwise operators on non-booleans produce invalid or unexpected JS.

### The Fix
Use **explicit comparisons**:
```python
disabled=UploadState.selected_files.length() == 0
disabled=(UploadState.is_uploading | UploadState.is_processing | (UploadState.uploaded_files.length() == 0))
```

### Rule
> **Never use bitwise `~`, `&`, `|` on lists, dicts, or objects inside `rx.Component` props. Use explicit boolean comparisons like `== 0` or `length() > 0`.**

---

## 4. Global Singletons Without Session Isolation

### What Went Wrong
The original app used global singleton services for `VectorStoreService` and `LLMService`:
```python
class LLMService:
    _instance = None  # Global singleton
```
This meant:
- **All users shared the same vectorstore and agent.**
- Calling `clear_history()` called `llm_service.reset()`, which destroyed the agent for **everyone** globally.
- Chat history memory used a hardcoded `thread_id = "main_conversation"`, so all users shared the same conversation context.

### The Fix
Use a **session-scoped registry** (`core/session_registry.py`) that maps each browser tab's `session_id` (a UUID stored in `BaseState`) to its own `{vectorstore, agent, docling_docs}`. When a user clears history, only their `thread_id` rotates; when they close the tab, their registry entry is dropped.

### Rule
> **Avoid global singletons for per-user resources in Reflex. Use a session registry keyed by a UUID stored in state.**

---

## 5. Calling Async Events from Sync Context Without `return`

### What Went Wrong
In `StructureState`, an async event was called from a sync method without returning it:
```python
@rx.event
def select_document(self, filename: str):
    self.selected_document = filename
    self.load_document_structure()  # Missing 'return'!
```
In Reflex, calling another event handler from inside an event handler just runs it as a normal method. To trigger it as a proper Reflex event (so it runs in the event loop and can be async), you must **return** it:
```python
    return StructureState.load_document_structure()
```

### The Fix
Always `return` event handlers when chaining them:
```python
@rx.event
def select_document(self, filename: str):
    self.selected_document = filename
    return StructureState.load_document_structure()
```

### Rule
> **When chaining event handlers inside another event handler, always `return` the event. Otherwise it runs synchronously as a plain method call.**

---

## 6. Chroma SQLite Thread-Safety

### What Went Wrong
Chroma's default in-memory backend uses SQLite, which is **not** thread-safe for concurrent writes from different asyncio tasks. The original app created the vectorstore inside a background task and searched from chat background tasks without isolation. Under load, this caused SQLite `OperationalError` or deadlocks.

### The Fix
Each session gets its own in-memory Chroma instance stored in the session registry. Because different sessions never share the same SQLite connection, there is no cross-session contention.

### Rule
> **If using Chroma (or any SQLite-backed store) with async/background tasks, isolate instances per session or protect access with locks.**

---

## 7. Upload Component Only Accepted PDFs

### What Went Wrong
The Streamlit app supported PDF, DOCX, PPTX, and HTML. The original Reflex upload zone only accepted PDF:
```python
accept={"application/pdf": [".pdf"]}
```

### The Fix
Expand the `accept` prop to cover all supported MIME types:
```python
accept={
    "application/pdf": [".pdf"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
    "text/html": [".html", ".htm"],
}
```
And update the core processor to route non-PDF files through Docling's generic `DocumentStream`.

### Rule
> **Keep feature parity with the reference implementation. If the Streamlit app supports multiple formats, the Reflex app must too.**

---

## Summary Checklist for Future Reflex Projects

1. **State vars are serializable only.** No objects with methods. No DB connections. No images.
2. **No `_private_vars` for background tasks.** Use public vars or external stores.
3. **No bitwise operators in JSX props.** Use explicit comparisons.
4. **No global singletons for user data.** Use session registries.
5. **Return chained events.** `return OtherState.event_name`.
6. **Isolate SQLite-backed stores per session.** No shared connections across async boundaries.
7. **Test multi-user isolation.** Open an incognito window after every feature change.

---

## Architecture That Works

The rebuilt app follows this strict flow:

1. **User uploads file** → Reflex event reads bytes → stores in module-level `_upload_buffers[session_id]`.
2. **Background task starts** → reads bytes from buffer → calls `core/document_processor.py` (pure Python) → gets `(documents, docling_docs)`.
3. **Vectorization** → calls `core/vector_store.py` → creates `Chroma` instance → stores in `session_registry[session_id]["vectorstore"]`.
4. **Agent creation** → calls `core/agent.py` → creates LangGraph agent → stores in `session_registry[session_id]["agent"]`.
5. **Chat** → `ChatState` retrieves agent from registry by `session_id` → streams tokens into `chat_history` (plain dicts).
6. **Structure viz** → `StructureState` retrieves `docling_docs` from registry → runs `DocumentStructureVisualizer` → assigns plain dicts to state.

This keeps Reflex state **100% serializable** and the backend **100% modular**.
