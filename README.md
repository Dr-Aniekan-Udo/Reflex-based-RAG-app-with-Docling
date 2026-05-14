# Reflex-based RAG App with Docling

A production-ready, multi-user Retrieval-Augmented Generation (RAG) application built with **Reflex**, **Docling**, **LangGraph**, and **Google Gemini**. This is the Reflex counterpart to the Streamlit-based version, rebuilt with strict serialization safety and session isolation.

## Features

- **Multi-Format Support**: PDF, DOCX, PPTX, HTML
- **Intelligent Parsing**: Docling with OCR, table structure extraction, and image detection
- **Memory-Safe Batching**: Large PDFs are processed in 50-page chunks with look-back overlap
- **Streaming Chat**: Real-time token-by-token responses with source citations
- **Document Analysis**: Summary, hierarchy, tables, and image metadata tabs
- **Multi-User Isolation**: Each browser session gets its own vector store and agent

## Tech Stack

- **Framework**: Reflex >= 0.8.24.post1
- **Document Parsing**: Docling [rapidocr] >=2.55.0
- **LLM Framework**: LangChain >=0.3.0, LangGraph >=0.2.0
- **LLM Provider**: Google Gemini (via `langchain-google-genai`)
- **Embeddings**: Google `embedding-001` (default); `text-embedding-004` available via env override

## Environment Variables
```bash
GOOGLE_API_KEY=your-google-api-key
GEMINI_MODEL=gemini-2.5-flash        # optional
EMBEDDING_MODEL=models/embedding-001   # optional (default)
```

### Environment Variables

Create a `.env` file in the project root:

```bash
GOOGLE_API_KEY=your-google-api-key
GEMINI_MODEL=gemini-2.5-flash               # optional
EMBEDDING_MODEL=models/text-embedding-004   # optional
```

### Run the App

```bash
reflex run
```

- Frontend: `http://localhost:3001`
- Backend API: `http://localhost:8002`

## Architecture

The project follows a strict three-layer architecture:

### 1. Core (`RAG_app/core/`)
Pure Python modules with **no Reflex imports**. Directly adapted from the working Streamlit `src/` logic.
- `document_processor.py` — Docling ingestion, batching, overlap
- `vector_store.py` — Chunking, embedding, Chroma creation
- `tools.py` — Agent search tool factory
- `agent.py` — LangGraph agent factory
- `structure.py` — Pre-serialization for Docling visualization
- `session_registry.py` — Session-scoped object registry

### 2. State (`RAG_app/state/`)
Reflex `rx.State` classes that hold **only serializable data** (`str`, `int`, `float`, `bool`, `list`, `dict`).
- `base_state.py` — `session_id`, theme, app initialization
- `upload_state.py` — File ingestion orchestration
- `chat_state.py` — Chat history & streaming
- `structure_state.py` — Document visualization state

### 3. UI (`RAG_app/components/`, `RAG_app/pages/`)
Reflex components with **zero business logic**.
- `layout.py` — Sidebar + main wrapper
- `upload.py` — File upload, progress, staging
- `chat.py` — Chat bubbles, input, streaming status
- `structure.py` — Document analysis tabs
- `dashboard.py` — Main page with tabs

### Multi-User Isolation
Each browser session receives a unique `session_id` stored in `BaseState`. The `session_registry` maps this ID to the session's vector store, agent, and raw Docling documents. When a session clears its data or the tab closes, the registry entry is dropped. This prevents cross-user contamination.

## Project Structure

```
RAG_app/
  core/
    __init__.py
    session_registry.py
    document_processor.py
    vector_store.py
    tools.py
    agent.py
    structure.py
  state/
    __init__.py
    base_state.py
    upload_state.py
    chat_state.py
    structure_state.py
  components/
    __init__.py
    layout.py
    upload.py
    chat.py
    structure.py
  pages/
    __init__.py
    dashboard.py
  RAG_app.py
assets/
  favicon.ico
  style.css
rxconfig.py
pyproject.toml
AGENTS.md
LESSONS_LEARNED.md
```

## Testing Strategy

Manual end-to-end test required after every significant change:

1. Upload a PDF (or DOCX/PPTX/HTML).
2. Verify processing completes without errors.
3. Ask a question; verify streaming and citations.
4. Check Document Analysis tabs.
5. Open an incognito window; verify sessions are isolated.

## Key Conventions

### No Non-Serializable Objects in State
You cannot store Docling `Document` objects, PIL images, Chroma instances, or LangGraph agents inside `rx.State`. Keep them in `core/session_registry.py`.

### No Private Variables for Background Tasks
Do not use `_uploaded_data` to pass data to `@rx.event(background=True)`. Use public state variables or module-level/session-scoped stores.

### No Bitwise Operators in Component Props
Never use `~`, `&`, `|` on lists/objects inside `rx.Component` props. Use explicit comparisons like `length() == 0`.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `TypeError` in upload component | Check for bitwise operators (`&`, `~`) in props. Use explicit comparisons. |
| Agent not initialized | Ensure documents are processed successfully. Check `session_registry` for the current `session_id`. |
| Documents not showing in Structure tab | Ensure `StructureState.load_available_documents` returns the event properly. |
| Cross-user data leakage | Verify each session has a unique `session_id` in `BaseState`. |

## License

MIT License
