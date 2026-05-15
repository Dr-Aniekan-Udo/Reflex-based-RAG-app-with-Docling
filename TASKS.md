# RAG App Development Tasks

## Completed ✅
- [x] Fix embedding count mismatch (manual upsert)
- [x] Document Analysis with HTML pre-rendering
- [x] Clear documents clears analysis state
- [x] Major UI/UX redesign (dark mode, orange theme, sidebar upload)
- [x] Fix Avatar color_scheme bug
- [x] Fix theme toggle (use rx.toggle_color_mode directly)
- [x] Constrain chat height to viewport
- [x] Fix button labels ("Clear Chat", "Clear")
- [x] Fix dark mode consistency (hardcoded colors)
- [x] Clean rebuild .web after reflex init corruption
- [x] **Celery + Redis architecture for per-document processing**
- [x] **Devcontainer updated with Redis auto-start**
- [x] **Per-document upload/processing/clear with DocumentItem model**
- [x] **350px sidebar with scrollable document cards**
- [x] **Process All / Clear All buttons**
- [x] **Stop button for individual document processing**
- [x] **Per-document vector store chunk tagging/deletion**
- [x] **CPU throttling and auto-retry in Celery tasks**

## Cancelled / Replaced
- ~~ProcessPoolExecutor for CPU-bound work~~ → Replaced by Celery+Redis
  - Reason: Cannot stop individual tasks, no per-doc status tracking, no retry logic

---

## Phase 1: Individual Document Processing with Celery+Redis (DONE)

All items implemented and committed.

### Architecture
```
Browser → Reflex Backend → Redis Broker → Celery Worker
                                              ↓
                                    Docling OCR (per doc)
                                    Chunking
                                    Embedding
                                    ↓
                                    Back to Reflex → Vector Store
```

### Key Features
- **Per-document cards** in sidebar with status-aware buttons
- **Additive upload**: Drop files → they append to list, never replace
- **Process/Stop/Reprocess/Retry/Clear** per document
- **Process All / Clear All** global actions
- **CPU throttling**: Worker checks CPU before starting, waits if >85%
- **Memory isolation**: `--max-tasks-per-child=1` kills worker after each doc
- **Auto-retry**: Failed docs retry 3x with exponential backoff
- **Real-time polling**: Background task polls Celery every 2s, updates progress
- **Persistent stats**: Files, Size, Pages, Vectors always visible at bottom

---

## Phase 2: Monitoring & Observability (Next)

### 2.1 LLM Observability with Langfuse
- [ ] Add `langfuse>=3.0` to dependencies
- [ ] Configure environment variables (`.env`):
  ```bash
  LANGFUSE_SECRET_KEY=sk-lf-...
  LANGFUSE_PUBLIC_KEY=pk-lf-...
  LANGFUSE_BASE_URL=https://cloud.langfuse.com
  ```
- [ ] Integrate `CallbackHandler` into `chat_state.py`
- [ ] Track per-session traces, token usage, latency, costs

### 2.2 Application Tracing with OpenTelemetry
- [ ] Add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`
- [ ] Auto-instrument FastAPI backend
- [ ] Custom spans for RAG pipeline stages

### 2.3 Health Check Endpoints
- [ ] `/health/live` (liveness)
- [ ] `/health/ready` (readiness - checks Redis, vector store)

---

## Phase 3: Intelligent Agent Orchestration (After Phase 2)

### 3.1 Enhanced RAG with ReAct Agent
- [ ] Refactor `agent.py` to use ReAct pattern
- [ ] Add reflection step for context sufficiency
- [ ] Multi-hop retrieval support

### 3.2 Plan-and-Execute for Complex Queries
- [ ] Planner node for breaking queries into sub-tasks
- [ ] Executor with sub-task routing
- [ ] Verification node

---

## Phase 4: Performance Optimization (After Phase 3)

### 4.1 Vector Store Optimization
- [ ] Persistent Chroma instead of in-memory
- [ ] HNSW index tuning
- [ ] Batch embedding optimization

### 4.2 Frontend Performance
- [ ] Virtualize long chat history
- [ ] Lazy load Document Analysis tabs
- [ ] Image lazy loading

### 4.3 Caching
- [ ] Cache Docling outputs
- [ ] Cache embedding results
- [ ] Redis cache for frequent queries

---

## Key Decisions Log

| Decision | Rationale |
|----------|-----------|
| **Celery+Redis over ProcessPoolExecutor** | Per-doc stop/retry, memory isolation, monitoring, horizontal scaling |
| **Local Redis over Upstash** | Free, zero latency, full control in Codespaces |
| **Per-document chunk tagging (doc_id)** | Allows individual doc removal without rebuilding vector store |
| **Sidebar 350px + scrollable docs** | Documents can grow infinitely; stats remain visible |
| **Additive upload (append, don't replace)** | Users can add docs incrementally without losing previous uploads |
| **Rate limiting: 2 docs/minute** | Prevents CPU saturation in Codespaces (2-core limit) |
| **Worker `--max-tasks-per-child=1`** | Kills process after each doc, prevents Docling memory leaks |
| **Polling every 2s for Celery status** | Simple, reliable, no WebSocket needed |

## Files Added/Modified in Phase 1

| File | Change |
|------|--------|
| `pyproject.toml` | Added celery, redis, psutil |
| `.devcontainer/devcontainer.json` | Added redis-server, port 6379 |
| `.devcontainer/post-create.sh` | Auto-start Redis on create |
| `RAG_app/core/celery_app.py` | NEW - Celery configuration with rate limiting, retries |
| `RAG_app/core/celery_tasks.py` | NEW - `process_document_task` with CPU throttling |
| `RAG_app/core/vector_store.py` | Added `add_documents()` for incremental upserts |
| `RAG_app/state/upload_state.py` | REFACTORED - DocumentItem model, per-doc events |
| `RAG_app/state/base_state.py` | Starts polling on page load |
| `RAG_app/components/layout.py` | REFACTORED - 350px sidebar, scrollable doc cards |
| `start_worker.sh` | NEW - Celery worker startup script |
