# AGENTS.md

## Project Overview

Reflex-based RAG (Retrieval-Augmented Generation) application with Docling for document parsing, LangGraph for agent orchestration, Chroma for vector storage, and Celery+Redis for background processing. This is the Reflex counterpart to the Streamlit-based version, rebuilt with strict serialization safety, session isolation, and production-grade observability.

## Architecture

### Layer Separation

The project is strictly split into three layers:

1. **Core (`RAG_app/core/`)**: Pure Python. No Reflex imports. Handles Docling, embeddings, vector stores, LangGraph agents, Celery tasks, and structure serialization.
2. **State (`RAG_app/state/`)**: Reflex `rx.State` classes. ONLY holds serializable data (str, int, float, bool, list, dict). Delegates all heavy lifting to Core via a session registry.
3. **UI (`RAG_app/components/`, `RAG_app/pages/`)**: Reflex components. Zero business logic. Only event wiring and display.

### Multi-User Isolation

- Each browser session gets a unique `session_id` (UUID) stored in `BaseState`.
- `core/session_registry.py` maintains a lightweight `dict` mapping `session_id` -> `{vectorstore, agent, docling_raw_docs}`.
- When a session clears its data or the tab closes, the registry entry is dropped.
- This prevents cross-user contamination and avoids global singletons.

### Background Processing (Celery + Redis)

CPU-bound Docling parsing runs in **Celery worker processes** to prevent blocking the Reflex event loop:

- **Broker**: Redis (`redis://localhost:6379/0`)
- **Worker pool**: `prefork` with concurrency=2
- **Model pre-warming**: Docling models loaded at worker startup via `worker_ready` signal
- **Memory management**: `worker_max_tasks_per_child=5` (restarts after 5 docs to clear accumulated memory)
- **Rate limiting**: `task_default_rate_limit="2/m"` (max 2 tasks per minute globally)
- **Task timeouts**: Hard limit 10 min, soft limit 8 min
- **Result backend**: Redis with 1-hour expiry, JSON serialization
- **Unified launcher**: `start.sh` handles Redis + Celery + Reflex startup

### Embedding Strategy

Due to a confirmed bug in `langchain-google-genai` (Issue #1704), `embed_documents()` returns incorrect counts when batching with `gemini-embedding-2-preview`.

**Workaround**: `RAG_app/core/embeddings.py` uses the **official `google-genai` SDK directly**:
- Pre-wraps each text in `Content(parts=[Part(text=...)])` before calling the API
- Batches up to 100 texts per call (Google's limit)
- Retries on 429 errors with exponential backoff (1s, 2s, 4s, 8s, 16s)
- Never silently skips chunks — raises on persistent failure

**Future**: When PR #1708 is merged into `langchain-google-genai`, we can revert to the LangChain wrapper.

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

### 5. Use Structured Logging (Not print())

**Rule**: All modules must use `structlog` via `from .logging_config import logger`. Never use `print()` for logging.

**Why**: The project configures `structlog` with JSON rendering, rotating file handlers (`logs/app.log`), and console output. Using `print()` bypasses all of this, making logs inconsistent and unparseable.

**Fix**: Import the logger and use keyword arguments:
```python
from .logging_config import logger

logger.info("event_name", key=value, key2=value2)
logger.warning("rate_limit_hit", attempt=attempt, wait_seconds=wait)
logger.error("task_failed", error=str(e), doc_id=doc_id)
```

### 6. Celery Task Result Serialization

**Rule**: Never call `self.update_state(state="FAILURE", meta={...})` manually in Celery tasks, and never call `self.retry()` with complex exception objects (e.g., Pydantic `ValidationError`).

**Why**: The JSON result backend requires `exc_type` in FAILURE metadata. Manual `update_state` can omit it, corrupting Redis storage and causing `ValueError: Exception information must include the exception type` on every subsequent access.

**Fix**: Return `{"success": False, "error": str(e)}` dict for failures. Use the UI's "Retry" button to re-queue tasks instead of Celery's automatic retry.

## Tech Stack

- **Framework**: Reflex >= 0.8.24.post1
- **Python**: >=3.12
- **Document Parsing**: Docling [rapidocr] >=2.55.0
- **LLM Framework**: LangChain >=0.3.0, LangGraph >=0.2.0
- **LLM Provider**: Google Gemini (via `langchain-google-genai`)
- **Embeddings**: Google `gemini-embedding-2-preview` (via `google-genai` SDK directly)
- **Background Tasks**: Celery >=5.3.0 + Redis >=5.0.0
- **Vector Store**: ChromaDB (in-memory per session)
- **Logging**: structlog with JSON output

## Environment Variables

Create a `.env` file in the project root:

```bash
# Required
GOOGLE_API_KEY=your-google-api-key

# Optional
GEMINI_MODEL=gemini-2.5-flash                        # LLM model selection
EMBEDDING_MODEL=gemini-embedding-2-preview           # Embedding model
EMBEDDING_BATCH_SIZE=100                             # Max texts per batch
EMBEDDING_RPM_LIMIT=5                                # Requests per minute
EMBEDDING_MAX_RETRIES=5                              # Retry attempts
HF_TOKEN=your-huggingface-token                      # Faster Docling downloads
REDIS_URL=redis://localhost:6379/0                   # Redis broker URL
```

## Build & Run

```bash
# Using UV (preferred)
uv sync

# Or using pip
pip install -r requirements.txt

# Run the app (unified launcher)
bash start.sh
```

The `start.sh` script:
1. Starts Redis server (or checks if running)
2. Applies Reflex polling transport patch (`patch_reflex_event.py`)
3. Purges old Celery task metadata from Redis
4. Purges Celery broker queue
5. Starts Celery worker with model pre-warming
6. Starts Reflex app

The frontend will be on `http://localhost:3001` and the backend API on `http://localhost:8002`.

## Project Structure

```
RAG_app/
  core/
    __init__.py
    session_registry.py      # Session-scoped object registry
    document_processor.py    # Docling ingestion, batching, overlap
    embeddings.py            # GeminiEmbedder (bypasses LangChain bug #1704)
    vector_store.py          # Chunking, embedding, Chroma creation
    celery_app.py            # Celery configuration with Redis broker
    celery_tasks.py          # CPU-bound document processing tasks
    tools.py                 # Agent search tool factory
    agent.py                 # LangGraph agent factory
    structure.py             # Pre-serialization for Docling visualization
    logging_config.py        # Structured logging with structlog
  state/
    __init__.py
    base_state.py            # session_id, theme, app initialization
    upload_state.py          # File ingestion orchestration with Celery polling
    chat_state.py            # Chat history & streaming
    structure_state.py       # Document visualization state
  components/
    __init__.py
    layout.py                # Sidebar + main wrapper
    upload.py                # File upload, progress, staging
    chat.py                  # Chat bubbles, input, streaming status
    structure.py             # Document analysis tabs
  pages/
    __init__.py
    dashboard.py             # Main page with tabs
  RAG_app.py                 # App factory & page registration
assets/
  favicon.ico
  style.css
  thumbnail.png              # Project screenshot for portfolio
rxconfig.py
pyproject.toml
.env.example
start.sh                     # Unified launcher (Redis + Celery + Reflex)
patch_reflex_event.py        # Polling transport patch for Codespaces
```

## Testing Strategy

Manual end-to-end test required after every significant change:
1. Upload a PDF (or DOCX/PPTX/HTML).
2. Verify processing completes.
3. Ask a question; verify streaming and citations.
4. Check Document Analysis tabs.
5. Open incognito window; verify isolation.

## Lessons Learned

### Lesson 1: Celery Redis Result Corruption

**Problem**: `ValueError: Exception information must include the exception type` spam every 2 seconds.

**Root cause**: Calling `self.update_state(state="FAILURE", meta={...})` in Celery tasks stores malformed metadata missing `exc_type`. Every subsequent `decode_result()` crashes.

**Fix**: Remove `self.update_state(state="FAILURE")` entirely. Return `{"success": False, "error": str(e)}` dict. Let Celery store the result as SUCCESS with our failure dict.

**Reference**: [Celery Issue #8457](https://github.com/celery/celery/issues/8457)

### Lesson 2: LangChain Batch Embedding Bug

**Problem**: `embed_documents(texts)` returns 1 embedding regardless of input count (9 texts -> 1 embedding, 80 texts -> 2 embeddings).

**Root cause**: `langchain-google-genai` passes bare `list[str]` to the Google GenAI SDK, which merges all texts into a single `Content` object. The API returns one embedding per `Content`, not per text.

**Fix**: Use `google-genai` SDK directly. Pre-wrap each text in `Content(parts=[Part(text=...)])` before calling `embed_content()`.

**Reference**: [LangChain Google Issue #1704](https://github.com/langchain-ai/langchain-google/issues/1704), [PR #1708](https://github.com/langchain-ai/langchain-google/pull/1708)

### Lesson 3: Docling Model Reload Overhead

**Problem**: Every document took 5-15 seconds to load Docling models from disk.

**Root cause**: `worker_max_tasks_per_child=1` killed the worker process after each task, evicting all models from RAM.

**Fix**: Changed to `worker_max_tasks_per_child=5`. Added `worker_ready` signal to pre-warm models at startup. First doc in a session loads models (~5s), next 4 docs are fast (~1s).

### Lesson 4: Google Free Tier Quota Limits

**Problem**: `429 RESOURCE_EXHAUSTED` after processing ~100 embedding requests.

**Root cause**: Google Gemini free tier allows 100 `embed_content` requests per day, not per minute.

**Mitigation**: Batch up to 100 chunks per API call (was 1 chunk per call before fix). Added exponential backoff retry. Future: consider local embeddings (`sentence-transformers`) as fallback.

### Lesson 5: Reflex Polling in Codespaces

**Problem**: WebSocket connections fail in GitHub Codespaces with `xhr poll error`.

**Root cause**: Reflex hardcodes `wss://` in `Endpoint.get_url()`, ignoring `transport="polling"` in `rxconfig.py`.

**Fix**: Monkey-patch Reflex source (`patch_reflex_event.py`) to respect the polling transport configuration.
