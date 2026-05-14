# RAG App Development Tasks

## Completed ✅
- [x] Fix embedding count mismatch (manual upsert)
- [x] Document Analysis with HTML pre-rendering
- [x] Clear documents clears analysis state
- [x] Major UI/UX redesign (dark mode, orange theme, sidebar upload)
- [x] Fix Avatar color_scheme bug
- [x] Fix theme toggle (use rx.toggle_color_mode directly)
- [x] Constrain chat height to viewport

---

## Phase 1: UI Polish (Next - 10 min)

### 1.1 Fix Button Labels
- [ ] **Chat Clear Button**: Change from `rx.icon("trash-2")` to `"Clear Chat"` text label
- [ ] **Upload Clear Button**: Change from `rx.icon("trash-2")` to `"Clear Uploads"` text label
- **Files**: `chat.py`, `layout.py`
- **Effort**: 5 minutes

### 1.2 Dark Mode Consistency (Low Priority)
- **Issue**: Hardcoded `color="gray"` and `color="white"` don't adapt properly
- **Root Cause**: 26 occurrences of hardcoded colors across components
- **Solution**: Replace with `rx.color_mode_cond()` or semantic color schemes
- **Files**: `chat.py`, `layout.py`, `structure.py`
- **Effort**: 30 minutes
- **Note**: Not blocking; cosmetic issue only

---

## Phase 2: Monitoring & Observability (High Priority)

### 2.1 LLM Observability with Langfuse
**Research Finding**: Langfuse is best for this stack (native LangGraph support, RAG-native traces, self-hostable)

**Tasks**:
- [ ] Add `langfuse>=3.0` to dependencies
- [ ] Configure environment variables (`.env`):
  ```bash
  LANGFUSE_SECRET_KEY=sk-lf-...
  LANGFUSE_PUBLIC_KEY=pk-lf-...
  LANGFUSE_BASE_URL=https://cloud.langfuse.com  # or self-hosted
  ```
- [ ] Integrate `CallbackHandler` into `chat_state.py`:
  ```python
  from langfuse.langchain import CallbackHandler
  langfuse_handler = CallbackHandler()
  
  # Pass to agent.astream(config={"callbacks": [langfuse_handler]})
  ```
- [ ] Track per-session traces, token usage, latency, costs
- [ ] Add metadata: session_id, thread_id, document names
- **Benefits**: Debug RAG retrieval, see which chunks are used, track costs
- **Effort**: 2 hours

### 2.2 Application Tracing with OpenTelemetry
**Research Finding**: Auto-instrument FastAPI (Reflex backend) for request tracing

**Tasks**:
- [ ] Add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi` to dependencies
- [ ] Configure OpenTelemetry tracer in `RAG_app.py`:
  ```python
  from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
  FastAPIInstrumentor.instrument_app(app)
  ```
- [ ] Add custom spans for RAG pipeline:
  - Document processing (Docling)
  - Embedding generation
  - Vector store creation
  - Agent inference
- [ ] Export traces to Jaeger or console (for development)
- **Benefits**: End-to-end request visibility, performance bottlenecks
- **Effort**: 3 hours

### 2.3 Health Check Endpoints
**Research Finding**: FastAPI health checks for liveness/readiness

**Tasks**:
- [ ] Add `/health/live` endpoint (liveness - app is running)
- [ ] Add `/health/ready` endpoint (readiness - dependencies OK)
- [ ] Check dependencies: vector store, agent, API key validity
- [ ] Return structured JSON health status
- **Benefits**: Kubernetes/Docker health checks, monitoring integration
- **Effort**: 1 hour

### 2.4 Structured Logging with Correlation IDs
**Research Finding**: Add trace context to all logs for request tracing

**Tasks**:
- [ ] Add `structlog.contextvars` for correlation IDs
- [ ] Inject session_id and request_id into all log entries
- [ ] Ensure logs are JSON-formatted for Loki ingestion
- **Effort**: 1 hour

---

## Phase 3: Concurrency & Background Jobs (High Priority)

### 3.1 ProcessPoolExecutor for CPU-Bound Work
**Research Finding**: Reflex background tasks run in asyncio event loop - NOT separate processes. Docling blocks all users.

**Architecture**:
```
Reflex Event Loop (asyncio)
├── @rx.event(bg=True) → Enqueue to ProcessPoolExecutor
└── Update state from results

ProcessPoolExecutor (multiprocessing)
├── Docling OCR (CPU-bound)
├── PDF Layout Analysis
├── Chunking + Embedding
└── Return results
```

**Tasks**:
- [ ] Create `RAG_app/core/worker.py` with `ProcessPoolExecutor` wrapper
- [ ] Refactor `upload_state.py`:
  - Start processing → submit to executor
  - Poll for completion via `asyncio.wrap_future()`
  - Update progress state incrementally
- [ ] Handle memory isolation (Docling leaks):
  - Option A: `max_workers=2` to limit memory
  - Option B: `max_tasks_per_child=1` (requires `concurrent.futures.pebble`)
- [ ] Add timeout handling (kill hung processes)
- **Benefits**: Non-blocking uploads, faster processing, no event loop blocking
- **Effort**: 4 hours

### 3.2 RQ (Redis Queue) for Production Scaling
**Research Finding**: RQ is best for multi-node deployments. Simpler than Celery.

**When to implement**:
- When you need multiple worker machines
- When ProcessPoolExecutor isn't enough

**Architecture**:
```
Reflex App → Redis → RQ Worker (separate process)
                    → RQ Worker (separate process)
```

**Tasks**:
- [ ] Add `redis>=5.0`, `rq>=2.0` to dependencies
- [ ] Configure Redis connection
- [ ] Create `process_documents_task` in `worker.py`
- [ ] Run worker: `rq worker document_processing --max-jobs 10`
- [ ] Refactor `upload_state.py` to enqueue + poll
- **Effort**: 4 hours (after ProcessPoolExecutor)

---

## Phase 4: Intelligent Orchestration (Medium-High Priority)

### 4.1 Enhanced RAG with ReAct Agent
**Pattern**: Interleave reasoning (Thought) → action (retrieve) → observation (chunks)

**Tasks**:
- [ ] Refactor `agent.py` to use ReAct pattern:
  ```python
  # Agent reasons about what to retrieve
  # Retrieves relevant chunks
  # Generates answer based on evidence
  ```
- [ ] Add reflection step: "Is the retrieved context sufficient?"
- [ ] Multi-hop retrieval: Follow up with additional searches if needed
- **Benefits**: Better answers for complex questions, self-correction
- **Effort**: 6 hours

### 4.2 Plan-and-Execute for Complex Queries
**Pattern**: Planner breaks query into sub-tasks, executor runs each

**Use Cases**:
- "Compare section 3 of doc A with section 5 of doc B"
- "Summarize all tables and list all images"
- "What are the differences between these two policies?"

**Tasks**:
- [ ] Add planner node to LangGraph
- [ ] Add executor node with sub-task routing
- [ ] Add verification node: "Does the answer fully address the query?"
- **Effort**: 8 hours

### 4.3 Context Compression
**Problem**: Long chat history + large documents exceed context window

**Solution**:
- [ ] Summarize old conversation turns
- [ ] Use sub-agents for investigation without polluting main context
- [ ] Implement sliding window for chat history
- **Effort**: 4 hours

---

## Phase 5: Performance Optimization (Medium Priority)

### 5.1 Vector Store Optimization
- [ ] Use persistent Chroma instead of in-memory (faster restart)
- [ ] Add index tuning (HNSW parameters)
- [ ] Batch embedding requests
- **Effort**: 3 hours

### 5.2 Frontend Performance
- [ ] Virtualize long chat history (rx.foreach can slow down with 100+ messages)
- [ ] Lazy load Document Analysis tabs
- [ ] Optimize image rendering (lazy load, thumbnails)
- **Effort**: 4 hours

### 5.3 Caching
- [ ] Cache Docling outputs (avoid re-parsing same PDF)
- [ ] Cache embedding results
- [ ] Add Redis cache layer for frequent queries
- **Effort**: 3 hours

---

## Phase 6: Advanced Features (Future)

### 6.1 Multi-Document Comparison
- [ ] Side-by-side document view
- [ ] Cross-document search and Q&A
- [ ] Diff/highlight mode

### 6.2 Long-Term Memory
- [ ] Remember user preferences across sessions
- [ ] Learn from feedback (thumbs up/down)
- [ ] Persistent conversation history

### 6.3 Multi-Modal Analysis
- [ ] Better image understanding (describe charts, diagrams)
- [ ] Audio/video transcription support
- [ ] OCR improvements

### 6.4 Collaboration
- [ ] Share sessions/links
- [ ] Export conversations
- [ ] Team workspaces

---

## Tool Comparison Reference

### Monitoring/Observability
| Tool | Best For | Self-Hosted | Cost | Integration Effort |
|------|----------|-------------|------|-------------------|
| **Langfuse** | LLM agents, RAG tracing | Yes | Free tier | 5 lines of code |
| Helicone | AI Gateway + observability | Yes | $79/mo Pro | Proxy-based |
| MLflow | ML lifecycle + LLM tracing | Yes | Free | 1 line autolog |
| Lunary | Lightweight alternative | Yes | Lower cost | Similar to Langfuse |

### Background Jobs
| Tool | Memory | Complexity | Best For |
|------|--------|------------|----------|
| **ProcessPoolExecutor** | Low | Very Low | Single-node, simple offloading |
| **RQ** | Low (~10MB) | Low | Multi-node, job persistence |
| Celery | High (~50MB+) | High | Complex workflows, distributed systems |
| Huey | Very low | Very low | Simple apps, SQLite backend |

### Agent Patterns
| Pattern | Use Case | Complexity |
|---------|----------|------------|
| **ReAct** | Multi-hop Q&A, tool use | Medium |
| Plan-and-Execute | Complex structured tasks | High |
| Reflexion | Iterative improvement | High |
| Multi-Agent | Team of specialists | Very High |

### Application Monitoring Stack (Recommended)
| Layer | Tool | Purpose |
|-------|------|---------|
| **Metrics** | Prometheus + `prometheus-client` | Request latency, RAG pipeline stages |
| **Dashboards** | Grafana | Visualize metrics |
| **Logs** | Grafana Loki + Promtail | Cheap log aggregation |
| **Traces** | OpenTelemetry → Jaeger/Tempo | End-to-end request tracing |
| **Health** | FastAPI routes | `/health/live`, `/health/ready` |

---

## Recommended Execution Order

1. **Week 1**: Phase 1 (UI polish) + Phase 2 (Langfuse + OpenTelemetry)
2. **Week 2**: Phase 3 (ProcessPoolExecutor)
3. **Week 3**: Phase 4.1 (ReAct agent)
4. **Week 4**: Phase 4.2 (Plan-and-Execute) + Phase 5 (Performance)
5. **Week 5+**: Phase 6 (Advanced features as needed)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     USER BROWSER                            │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Sidebar   │  │   Chat Tab      │  │  Analysis Tab   │ │
│  │  (Upload)   │  │  (Full-width)   │  │  (Tabs/Cards)   │ │
│  └─────────────┘  └─────────────────┘  └─────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                  REFLEX BACKEND (asyncio)                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  UploadState    │  │  ChatState      │  │  Structure  │ │
│  │  (enqueues)     │  │  (streaming)    │  │  State      │ │
│  └────────┬────────┘  └─────────────────┘  └─────────────┘ │
│           │                                                 │
│  ┌────────┴─────────────────────────────────────────────┐  │
│  │         ProcessPoolExecutor (multiprocessing)        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │  │
│  │  │  Docling    │  │  Embeddings │  │  Vector     │ │  │
│  │  │  (OCR)      │  │  (Gemini)   │  │  Store      │ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐│
│  │  Monitoring (Langfuse + OpenTelemetry)                  ││
│  │  - LLM traces, tokens, costs                           ││
│  │  - Request latency, errors                             ││
│  │  - Health endpoints                                    ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## Notes

- **Dark mode issue**: Hardcoded colors need `rx.color_mode_cond()` replacement. Not blocking.
- **ProcessPoolExecutor**: Requires `multiprocessing` safe imports (no Reflex imports in worker module).
- **Langfuse self-hosted**: Use Docker Compose for local development.
- **All changes should follow AGENTS.md conventions**: No non-serializable objects in state, use session registry for backend objects.
- **Reflex background tasks**: Run in asyncio event loop. Only use for I/O, never CPU-bound work.
