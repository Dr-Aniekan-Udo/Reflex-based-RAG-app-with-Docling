# AGENTS.md

## Project Overview
Reflex-based RAG (Retrieval-Augmented Generation) application with Docling for document parsing, LangGraph for agent orchestration, and Chroma for vector storage. This is the Reflex counterpart to the Streamlit-based version.

## Architecture

### Layer Separation
The project is strictly split into three layers:

1. **Core (`RAG_app/core/`)**: Pure Python. No Reflex imports. Handles Docling, embeddings, vector stores, LangGraph agents, and structure serialization. This is directly ported from the working Streamlit `src/` modules.
2. **State (`RAG_app/state/`)**: Reflex `rx.State` classes. ONLY holds serializable data (str, int, float, bool, list, dict). Delegates all heavy lifting to Core via a session registry.
3. **UI (`RAG_app/components/`, `RAG_app/pages/`)**: Reflex components. Zero business logic. Only event wiring and display.

### Multi-User Isolation
- Each browser session gets a unique `session_id` (UUID) stored in `BaseState`.
- `core/session_registry.py` maintains a lightweight `dict` mapping `session_id` -> `{vectorstore, agent, docling_raw_docs}`.
- When a session is cleared or the tab closes, the registry entry is dropped.
- This prevents cross-user contamination and avoids global singletons.

## Critical Conventions

### 1. No Non-Serializable Objects in Reflex State
**Rule**: You CANNOT store Docling `Document` objects, PIL images, Chroma `VectorStore` instances, LangGraph agents, or any custom class with methods inside any `rx.State` subclass.
**Why**: Reflex pickles/synchronizes state between backend and frontend. Non-serializable objects crash the event loop or corrupt state.
**Fix**: Keep backend objects in `core/session_registry.py`. Pre-serialize visualization data into plain Python dicts/lists before assigning to state.

### 2. No Private Variables for Cross-Task Data
**Rule**: Do NOT use leading-underscore variables (e.g., `_uploaded_data`) to pass data between normal events and `@rx.event(background=True)` tasks.
**Why**: Reflex may strip, ignore, or fail to sync private variables across background task boundaries.
**Fix**: Use public state variables, or pass the data directly as arguments to the background event handler.

### 3. No Bitwise Operators in Component Props
**Rule**: Never use Python bitwise operators (`~`, `&`, `|`) inside `rx.Component` props for boolean logic.
**Why**: Reflex transpiles component code to React/TypeScript. Python bitwise `~` on a list raises `TypeError`.
**Fix**: Use explicit comparisons: `disabled=(State.my_list.length() == 0)` or `disabled=(State.is_processing | State.is_uploading)` (boolean OR is fine, bitwise `&` on lists is NOT).

### 4. Thread-Safe Vector Store Access
**Rule**: Chroma's in-memory SQLite backend is NOT thread-safe for concurrent writes/reads from different asyncio tasks.
**Fix**: All Chroma creation and search operations originating from different sessions should be protected if sharing a process. In this architecture, each session gets its own in-memory Chroma instance stored in the registry, so there is no cross-session SQLite contention.

## Tech Stack
- **Framework**: Reflex >= 0.8.24.post1
- **Python**: >=3.12
- **Document Parsing**: Docling [rapidocr] >=2.55.0
- **LLM Framework**: LangChain >=0.3.0, LangGraph >=0.2.0
- **LLM Provider**: Google Gemini (via `langchain-google-genai`)
- **Embeddings**: Google `text-embedding-004`
- **Vector DB**: ChromaDB (in-memory per session)
- **Frontend Styling**: Tailwind CSS v4 (via Reflex plugin)

## Environment Variables
Create a `.env` file in the project root:
```bash
GOOGLE_API_KEY=your-google-api-key
GEMINI_MODEL=gemini-2.5-flash        # optional
EMBEDDING_MODEL=models/text-embedding-004  # optional
```

## Build & Run
```bash
# Using UV (preferred)
uv sync

# Or using pip
pip install -r requirements.txt

# Run the app
reflex run
```
The frontend will be on `http://localhost:3001` and the backend API on `http://localhost:8002`.

## Project Structure
```
RAG_app/
  core/
    __init__.py
    session_registry.py   # Session-scoped object registry
    document_processor.py # Docling ingestion, batching, overlap
    vector_store.py       # Chunking, embedding, Chroma creation
    tools.py              # Agent search tool factory
    agent.py              # LangGraph agent factory
    structure.py          # Pre-serialization for Docling visualization
  state/
    __init__.py
    base_state.py         # session_id, theme, user
    upload_state.py       # File ingestion orchestration
    chat_state.py         # Chat history & streaming
    structure_state.py    # Document visualization state
  components/
    __init__.py
    layout.py             # Sidebar + main wrapper
    upload.py             # File upload, progress, staging
    chat.py               # Chat bubbles, input, streaming status
    structure.py          # Document analysis tabs
  pages/
    __init__.py
    dashboard.py          # Main page with tabs
  RAG_app.py              # App factory & page registration
assets/
  favicon.ico
  style.css
rxconfig.py
pyproject.toml
```

## Testing Strategy
- Manual end-to-end test required after every significant change:
  1. Upload a PDF (or DOCX/PPTX/HTML).
  2. Verify processing completes.
  3. Ask a question; verify streaming and citations.
  4. Check Document Analysis tabs.
  5. Open incognito window; verify isolation.
