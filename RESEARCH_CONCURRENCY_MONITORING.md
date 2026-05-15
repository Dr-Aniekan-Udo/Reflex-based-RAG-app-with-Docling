# Research Report: Python Concurrency & Application Monitoring for RAG Applications

> **Project**: Reflex-based RAG app with Docling
> **Date**: 2026-05-15
> **Focus**: Production-ready, self-hostable solutions

---

## Topic 1: Python Concurrency Patterns for RAG Applications

### 1. Multiprocessing vs Multithreading vs Asyncio

Python offers three primary concurrency models, each suited to different workload types. The Global Interpreter Lock (GIL) is the critical differentiator: it allows only one thread to execute Python bytecode at a time, making multithreading ineffective for CPU-bound work.

#### Comparison Table

| Dimension | `asyncio` | `threading` | `multiprocessing` |
|-----------|-----------|-------------|-------------------|
| **Best For** | I/O-bound (network, files) | I/O-bound with blocking libraries | CPU-bound (compute, OCR, ML inference) |
| **GIL Impact** | Cooperative multitasking; GIL released during I/O waits | Preemptive; GIL limits parallelism to 1 core | Bypasses GIL entirely; true parallelism on multiple cores |
| **Memory Model** | Shared (single process) | Shared (single process) | Isolated (separate processes, copy-on-write) |
| **Overhead** | Lowest (coroutines) | Medium (thread stacks ~8MB) | Highest (process fork/spawn + serialization) |
| **Data Sharing** | Direct (same memory) | Direct (needs locks) | `multiprocessing.Queue`, `Manager`, pickling |
| **Use in RAG** | API calls (Gemini embeddings), streaming | Legacy sync I/O wrappers | Docling OCR/layout analysis, PDF parsing |
| **Crash Isolation** | None (crashes entire app) | None (crashes entire app) | Strong (worker dies, main process survives) |

#### RAG-Specific Mapping

| Pipeline Stage | Workload Type | Recommended Model | Rationale |
|----------------|---------------|-------------------|-----------|
| **File Upload (read bytes)** | I/O-bound | `asyncio` | Non-blocking read from network buffer |
| **Docling OCR + Layout** | CPU-bound | `multiprocessing` | Heavy ONNX/TensorFlow inference; GIL-bound |
| **PDF Batch Splitting** | Mixed | `asyncio` → offload to `ProcessPoolExecutor` | I/O to read, CPU to split |
| **Embedding Generation** | I/O-bound (API call) | `asyncio` | Waiting on Gemini API latency (~100-500ms) |
| **Vector Store Creation** | CPU-bound (Chroma/SQLite) | `threading` or main thread | In-memory SQLite; thread-safe for reads, NOT concurrent writes |
| **Agent Inference (LLM)** | I/O-bound (API call) | `asyncio` | Streaming tokens from Gemini |
| **Document Serialization** | CPU-bound | `multiprocessing` | Large object tree traversal |

#### Critical Rule for This Project

Docling's OCR pipeline uses RapidOCR (ONNX Runtime) and layout models. These release the GIL *during* the actual C++ inference, but the surrounding Python orchestration (image preprocessing, tensor manipulation) is still GIL-contended. For multi-page PDFs with batch size 50, processing blocks the event loop for **seconds to minutes**, freezing all other user sessions in a single-process Reflex deployment.

---

### 2. Reflex Background Events Deep Dive

Reflex background events (`@rx.event(background=True)`) are the framework's mechanism for long-running tasks that need to yield state updates to the frontend.

#### How It Works Internally

1. **Queueing**: When a background event is triggered, Reflex serializes the event arguments and enqueues it into an **asyncio task queue** associated with the user's session.
2. **Execution**: The task runs as a Python `asyncio.Task` within the **same event loop** as the main Reflex backend. It is NOT a separate OS thread or process.
3. **State Synchronization**: Inside the background task, `async with self:` acquires a lock on the state instance, applies mutations, and serializes the delta back to the frontend via WebSocket or Server-Sent Events (SSE).
4. **Yielding**: `yield` statements inside `async with self:` flush state updates to the client without returning from the task.

#### Official Documentation Reference

> Background events run in the same Python process as the main app server. They are executed as asyncio tasks on the event loop. This means they are cooperative, not parallel — a CPU-intensive background task will block the entire event loop and prevent other requests from being handled.
> — [Reflex Background Events Docs](https://reflex.dev/docs/events/background-events/)

#### Limitations

| Limitation | Detail | Impact on RAG App |
|------------|--------|-------------------|
| **Same Event Loop** | Background tasks are `asyncio.Task`s, not threads | Docling blocks ALL users |
| **GIL Contention** | CPU work in background task starves the loop | Frontend becomes unresponsive |
| **Shared Memory** | All sessions share one process's heap | Docling memory leaks accumulate across sessions |
| **No Timeout** | Reflex does not enforce a task timeout | Runaway OCR hangs forever |
| **Pickling Constraints** | State must be serializable | Cannot store `Document` objects in state |
| **No True Parallelism** | Only one background task runs per event loop tick at a time | Multiple uploads queue serially |

#### Why It Blocks for Docling

In `upload_state.py`, `start_processing()` calls:

```python
processor = DocumentProcessor()
documents, docling_docs = processor.process_uploaded_files(file_data)
```

`process_uploaded_files` is a **synchronous, CPU-bound** function. Even though it's called inside an `async def` background task, it runs on the event loop thread. The GIL is held for the duration of every Python bytecode instruction. ONNX Runtime may release the GIL during model inference, but the preprocessing and postprocessing dominate for document parsing.

**Result**: While User A's PDF is being OCR'd, User B cannot even load the page. The backend is frozen.

---

### 3. Integration Patterns

#### Pattern A: Reflex BG Task + ProcessPoolExecutor (Recommended for Single-Node)

Offload the CPU-intensive Docling work to a `ProcessPoolExecutor`, while keeping the Reflex state orchestration in the async event loop.

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
import reflex as rx
from functools import partial

# Global executor (or managed via lifespan)
_process_pool: ProcessPoolExecutor | None = None

def get_process_pool() -> ProcessPoolExecutor:
    global _process_pool
    if _process_pool is None:
        # max_workers = CPU cores; mp_context='spawn' for isolation on macOS/Windows
        _process_pool = ProcessPoolExecutor(
            max_workers=max(1, os.cpu_count() or 1),
            mp_context="spawn"  # Required for clean Docling initialization
        )
    return _process_pool

# Module-level pure function for pickling
def _process_files_in_worker(file_data: list[tuple[str, bytes]]) -> dict:
    """Runs in a separate Python process. Must be picklable."""
    from docling.document_converter import DocumentConverter
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    # ... (Docling setup and processing)
    # Return plain Python dicts/lists ONLY
    return {
        "documents": [...],  # plain text/metadata
        "docling_docs": [...],  # serialized structure data
        "total_pages": 42,
    }

class UploadState(rx.State):
    @rx.event(background=True)
    async def start_processing(self):
        pool = get_process_pool()
        loop = asyncio.get_running_loop()

        # Run CPU-bound work in process pool without blocking the event loop
        result = await loop.run_in_executor(
            pool,
            _process_files_in_worker,
            file_data,
        )

        async with self:
            self.process_progress = 40
            self.current_task_message = f"Processed {result['total_pages']} pages..."

        # Continue with I/O-bound vectorization (can stay in event loop)
        vs_manager = VectorStoreManager()
        # ...
```

**Architecture Flow:**

```
Browser → WebSocket → Reflex Event Loop (asyncio)
                              │
                              ├──> Fast I/O (state updates, API calls) — stays in loop
                              │
                              └──> loop.run_in_executor(ProcessPoolExecutor, _process_files_in_worker)
                                           │
                                           └──> [Separate OS Process]
                                                ├──> Docling OCR/Layout (CPU-bound, GIL bypassed)
                                                └──> Returns plain dict (pickled)
```

#### Pattern B: Reflex BG Task → RQ Worker (Recommended for Multi-Node)

For horizontal scaling or strict memory isolation, use RQ (Redis Queue) workers running on separate machines or containers.

```python
# worker_jobs.py — This file is imported by the RQ worker process
from rq import Queue
from redis import Redis

redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
queue = Queue(connection=redis_conn)

def process_document_task(file_data: list, session_id: str):
    """Executed by RQ worker in a separate process/container."""
    processor = DocumentProcessor()
    documents, docling_docs = processor.process_uploaded_files(file_data)
    # Store results in Redis or shared volume for polling
    redis_conn.setex(
        f"rag:result:{session_id}",
        3600,
        json.dumps({"status": "complete", "chunks": len(documents)})
    )
    return {"chunks": len(documents)}

# In Reflex state
class UploadState(rx.State):
    @rx.event(background=True)
    async def start_processing(self):
        # Enqueue job; returns immediately
        job = queue.enqueue(process_document_task, file_data, self.session_id)

        # Poll for completion (every 2 seconds)
        while True:
            await asyncio.sleep(2)
            result_raw = redis_conn.get(f"rag:result:{self.session_id}")
            if result_raw:
                result = json.loads(result_raw)
                async with self:
                    self.process_progress = 100
                    self.current_task_message = "Done!"
                break
```

**Architecture Flow:**

```
Reflex App Server (asyncio)          Redis (Broker)          RQ Worker Pool (separate containers)
       │                                    │                              │
       ├── enqueue(process_document_task) ─>│                              │
       │                                    │── job_id:xxx ───────────────>│
       │                                    │                              ├──> process_document_task()
       │<─── poll every 2s ─────────────────│<── result stored ────────────│      (Docling, CPU-heavy)
       │                                    │                              └──> result in Redis
       │<─── result found ──────────────────│
```

#### Pattern C: Hybrid Approach (Ultimate Flexibility)

| Tier | Technology | Responsibility |
|------|------------|----------------|
| **Frontend** | Reflex UI | File drop, progress bars, chat |
| **API/State** | Reflex `@rx.event(background=True)` | Session management, polling, streaming |
| **I/O Tasks** | `asyncio` / `aiohttp` | Gemini API calls, embedding requests, webhooks |
| **CPU Tasks** | `ProcessPoolExecutor` | Single-node Docling, small deployments |
| **CPU Tasks (scale)** | RQ + Redis | Multi-node Docling, strict isolation, large queues |
| **Results** | Redis / Chroma | Vector store, session cache, job status |

---

### 4. ProcessPoolExecutor vs RQ vs Celery

#### Comparison Table

| Dimension | `ProcessPoolExecutor` | **RQ** | **Celery** |
|-----------|----------------------|--------|------------|
| **Complexity** | Low (stdlib) | Medium | High |
| **Broker Required** | None (in-process) | Redis/Valkey | Redis/RabbitMQ/SQS |
| **Worker Model** | Process pool | Forked worker processes | Prefork/Eventlet/Gevent/Threads |
| **Persistence** | In-memory only (jobs lost on restart) | Redis-backed | Result backend (Redis/DB/etc.) |
| **Scheduling** | Immediate only | `enqueue_at`, `enqueue_in`, repeats | Crontab, intervals, complex workflows (Canvas) |
| **Retries** | Manual | Built-in (`Retry(max=3)`) | Built-in (`autoretry_for`, exponential backoff) |
| **Monitoring** | None | Built-in CLI + `rq-dashboard` | Flower, extensive events |
| **Memory Isolation** | Strong (spawn) | Strong (fork/spawn) | Strong (prefork) |
| **Docling Leaks** | Worker restart via `max_tasks_per_child` | Worker restart via `--max-jobs` | Worker restart via `--max-tasks-per-child` |
| **Serialization** | `pickle` (must be picklable) | `pickle` | `pickle` / `json` / `msgpack` |
| **Best For** | Single-node apps, simplicity | Small-medium apps, job queues | Large distributed systems, complex pipelines |
| **Self-Hosting Ease** | Trivial (no infra) | Easy (Redis + `rq worker`) | Moderate (broker + backend + workers) |

#### Docling Memory Leak Mitigation

Docling and its underlying ML frameworks (ONNX Runtime, PyTorch) are known to leak GPU/CPU memory across conversions. **Worker restart** is the only reliable fix.

```python
# ProcessPoolExecutor: workers auto-restart after N tasks
ProcessPoolExecutor(
    max_workers=4,
    mp_context="spawn",
    initializer=_init_worker,
    initargs=(...)
)
# Note: stdlib ProcessPoolExecutor does NOT have max_tasks_per_child.
# Use pebble.ProcessPool for that, or manage manually.

# RQ: restart worker after N jobs
# $ rq worker --with-scheduler --max-jobs 10

# Celery: restart worker after N tasks
# $ celery -A tasks worker --max-tasks-per-child=10
```

**Recommendation for this RAG app**: Start with `ProcessPoolExecutor` for simplicity on a single node. Migrate to **RQ** when you need multi-node scaling or job persistence. Avoid Celery unless you need its workflow orchestration (chains, chords, Canvas).

#### ProcessPoolExecutor with Asyncio: Complete Example

```python
import asyncio
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any

class HybridProcessor:
    """Hybrid CPU+I/O processor using asyncio + ProcessPoolExecutor."""

    def __init__(self, max_workers: int | None = None):
        self.max_workers = max_workers or max(1, (os.cpu_count() or 1) - 1)
        self._executor: ProcessPoolExecutor | None = None

    @property
    def executor(self) -> ProcessPoolExecutor:
        if self._executor is None or self._executor._shutdown:
            self._executor = ProcessPoolExecutor(
                max_workers=self.max_workers,
                mp_context="spawn",
            )
        return self._executor

    async def process_documents(self, file_data: list[tuple[str, bytes]]) -> dict[str, Any]:
        loop = asyncio.get_running_loop()

        # 1. CPU-bound: offload to process pool
        raw_result = await loop.run_in_executor(
            self.executor,
            _sync_process_documents,
            file_data,
        )

        # 2. I/O-bound: stay in asyncio event loop
        embeddings = await self._generate_embeddings_async(raw_result["texts"])

        return {**raw_result, "embeddings": embeddings}

    async def _generate_embeddings_async(self, texts: list[str]) -> list[list[float]]:
        """Batch async embedding calls (pseudo-async wrapper around sync API)."""
        # If the embedding client is sync, use run_in_executor with ThreadPoolExecutor
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_embed, texts)

    async def shutdown(self):
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None


def _sync_process_documents(file_data: list[tuple[str, bytes]]) -> dict[str, Any]:
    """PURE FUNCTION: runs in separate process. No closures, no unpicklable objects."""
    from docling.document_converter import DocumentConverter
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    # ... process files ...
    return {"texts": [...], "metadata": [...]}


def _sync_embed(texts: list[str]) -> list[list[float]]:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2-preview")
    return embeddings.embed_documents(texts)
```

---

## Topic 2: Application Monitoring (Beyond LLM Observability)

### 1. OpenTelemetry

OpenTelemetry is the CNCF standard for observability. It provides a unified API for **traces**, **metrics**, and **logs**.

#### Python SDK Integration

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi
pip install opentelemetry-exporter-otlp opentelemetry-exporter-jaeger
```

```python
# RAG_app/telemetry.py
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

resource = Resource(attributes={SERVICE_NAME: "rag-app"})
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"))
)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)


def instrument_app(app):
    """Call this on the underlying FastAPI app."""
    FastAPIInstrumentor.instrument_app(app)
```

> **Reflex Integration Note**: Reflex wraps a FastAPI app internally. You can access it via `app.api` (if exposed) or instrument at the ASGI level. Reflex 0.8.x exposes the FastAPI instance; check `rx.App().app` or use middleware.

#### Auto-Instrumentation for FastAPI (Reflex Backend)

```python
# rxconfig.py or RAG_app.py
from reflex import App
from .telemetry import instrument_app

app = App()
# Reflex stores the FastAPI instance internally; instrument it:
instrument_app.app = app.app  # Depending on Reflex version, access may vary
```

Alternatively, use the OpenTelemetry Python agent (zero-code):

```bash
opentelemetry-instrument \
  --traces_exporter console,otlp \
  --metrics_exporter prometheus \
  --service_name rag-app \
  reflex run
```

#### Tracing Requests End-to-End

Create custom spans for RAG-specific operations:

```python
from opentelemetry import trace

tracer = trace.get_tracer("rag.pipeline")

async def process_and_index(session_id: str, file_data: list):
    with tracer.start_as_current_span("document.ingestion") as span:
        span.set_attribute("session.id", session_id)
        span.set_attribute("file.count", len(file_data))

        with tracer.start_as_current_span("docling.ocr"):
            docs = processor.process(file_data)

        with tracer.start_as_current_span("embedding.generation"):
            embeddings = await generate_embeddings(docs)

        with tracer.start_as_current_span("vectorstore.upsert"):
            store.upsert(embeddings)
```

#### Exporting to Jaeger / Zipkin

| Exporter | Endpoint | Self-Hostable |
|----------|----------|---------------|
| **Jaeger** | `http://jaeger:4317` (gRPC) or `14268` (HTTP) | Yes (`jaegertracing/all-in-one` Docker image) |
| **Zipkin** | `http://zipkin:9411` | Yes (`openzipkin/zipkin` Docker image) |
| **Tempo** | `http://tempo:4317` | Yes (Grafana stack) |
| **OTLP Collector** | `http://otel-collector:4317` | Yes (CNCF collector, fans out to multiple backends) |

**Recommended**: Deploy the **OpenTelemetry Collector** as a sidecar. It receives OTLP from the app and exports to Jaeger (traces), Prometheus (metrics), and Loki (logs) simultaneously.

---

### 2. Prometheus + Grafana

#### Python Client Setup

```bash
pip install prometheus-client
```

```python
# RAG_app/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
import time

# Custom RAG metrics
DOCUMENTS_PROCESSED = Counter(
    "rag_documents_processed_total",
    "Total documents ingested",
    ["status"]  # status: success | error
)

TOKENS_CONSUMED = Counter(
    "rag_tokens_consumed_total",
    "LLM tokens used",
    ["model", "operation"]  # operation: embedding | generation
)

PROCESSING_DURATION = Histogram(
    "rag_processing_duration_seconds",
    "Time spent processing documents",
    ["stage"],  # stage: ocr | chunking | embedding | indexing
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

ACTIVE_SESSIONS = Gauge(
    "rag_active_sessions",
    "Currently active user sessions"
)

APP_INFO = Info("rag_app", "Application metadata")
APP_INFO.info({"version": "1.0.0", "framework": "reflex"})


async def metrics_middleware(request: Request, call_next):
    """FastAPI middleware to expose /metrics and track request latency."""
    if request.url.path == "/metrics":
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    REQUEST_DURATION.labels(method=request.method, endpoint=request.url.path).observe(duration)
    return response
```

#### Metrics to Track for RAG

| Category | Metric Name | Type | Labels |
|----------|-------------|------|--------|
| **HTTP** | `http_request_duration_seconds` | Histogram | `method`, `endpoint`, `status` |
| **HTTP** | `http_requests_total` | Counter | `method`, `endpoint`, `status` |
| **RAG** | `rag_documents_processed_total` | Counter | `status` |
| **RAG** | `rag_processing_duration_seconds` | Histogram | `stage` |
| **RAG** | `rag_chunks_created_total` | Counter | `source` |
| **RAG** | `rag_tokens_consumed_total` | Counter | `model`, `operation` |
| **RAG** | `rag_vector_search_duration_seconds` | Histogram | `k` |
| **System** | `process_resident_memory_bytes` | Gauge | — |
| **Business** | `rag_active_sessions` | Gauge | — |
| **Business** | `rag_questions_answered_total` | Counter | `source` (retrieved vs fallback) |

#### Grafana Dashboards

Deploy Grafana with Prometheus data source and create dashboards for:
1. **Overview**: Request rate, error rate, P95 latency (RED method)
2. **RAG Pipeline**: Documents/min, processing time per stage, token burn rate
3. **System**: Memory per worker, CPU utilization, disk I/O
4. **Business**: Active users, questions/session, citation accuracy

**Self-hosted stack** (single `docker-compose.yml`):
- Prometheus (`prom/prometheus`)
- Grafana (`grafana/grafana`)
- Node Exporter (`prom/node-exporter`)
- cAdvisor (`google/cadvisor`) for container metrics

---

### 3. Reflex Built-in Telemetry

Reflex includes optional telemetry that reports anonymized usage data to the Reflex team.

#### What `telemetry_enabled=False` Disables

| Data Point | Disabled? |
|------------|-----------|
| Framework version | Yes |
| Python version | Yes |
| OS/platform | Yes |
| CPU count | Yes |
| Memory size | Yes |
| Event counts (page loads, state updates) | Yes |
| Error counts (anonymized stack traces) | Yes |

**What it does NOT disable**:
- Reflex does NOT expose application metrics, health endpoints, or profiling data.
- There is no built-in `/metrics`, `/health`, or `/ready` endpoint.
- You must build all production monitoring yourself.

#### Configuration

```python
# rxconfig.py
import reflex as rx

config = rx.Config(
    app_name="RAG_app",
    telemetry_enabled=False,  # Disable Reflex telemetry
)
```

---

### 4. Health Checks

#### Best Practices for FastAPI Health Endpoints

Reflex uses FastAPI under the hood. Add custom API routes for health probes.

```python
# RAG_app/health.py
from fastapi import APIRouter, HTTPException
import chromadb
from langchain_chroma import Chroma

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/live")
async def liveness():
    """K8s liveness probe: is the process running?"""
    return {"status": "alive"}

@router.get("/ready")
async def readiness():
    """K8s readiness probe: can the app serve traffic?"""
    checks = {}

    # Check vector store connectivity (if persistent Chroma)
    try:
        # For in-memory Chroma, this is always true;
        # for persistent Chroma, verify directory access.
        checks["vectorstore"] = "ok"
    except Exception as e:
        checks["vectorstore"] = f"error: {e}"
        raise HTTPException(status_code=503, detail=checks)

    # Check external API (Gemini) — lightweight
    try:
        # Option 1: ping Google's API status endpoint
        # Option 2: attempt a dummy embedding (costs tokens; avoid in tight loops)
        checks["gemini_api"] = "ok"
    except Exception as e:
        checks["gemini_api"] = f"error: {e}"
        raise HTTPException(status_code=503, detail=checks)

    return {"status": "ready", "checks": checks}

@router.get("/metrics")
async def metrics():
    """Prometheus scrape endpoint."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from starlette.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

```python
# Register in RAG_app.py or rxconfig.py
from RAG_app.health import router as health_router

# Reflex exposes an internal FastAPI app at app.app
app = rx.App()
app.app.include_router(health_router)
```

#### Readiness vs Liveness Probes

| Probe | Question | Failure Action | Endpoint |
|-------|----------|----------------|----------|
| **Liveness** | Is the process running? | K8s restarts the container | `/health/live` |
| **Readiness** | Is the app ready to accept traffic? | K8s removes pod from service | `/health/ready` |
| **Startup** | Has the app finished initializing? | K8s waits, then liveness | `/health/ready` (combined) |

---

### 5. Log Aggregation

The project already uses `structlog` with JSON rendering — excellent foundation.

#### Structured Logging (Current Implementation)

```python
# RAG_app/core/logging_config.py (existing — good)
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    # ...
)
```

**Improvements to add**:
1. **Correlation IDs**: Inject a `request_id` / `session_id` into every log entry for a given request.
2. **Contextvars binding**: Use `structlog.contextvars.bind_contextvars(request_id=...)` so async tasks automatically inherit the ID.

```python
import uuid
from structlog.contextvars import bind_contextvars, clear_contextvars

async def add_correlation_id(request):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    bind_contextvars(request_id=request_id, session_id=getattr(request.state, "session_id", None))

# Add as FastAPI middleware
```

#### ELK vs Loki vs Self-Hosted

| Solution | Storage | Query Language | Resource Usage | Best For |
|----------|---------|----------------|----------------|----------|
| **ELK Stack** (Elasticsearch + Logstash + Kibana) | Inverted index (high disk) | Lucene/KQL | High RAM/CPU | Full-text search, complex analytics |
| **Grafana Loki** | Object storage (S3/FS) + small index | LogQL (Prometheus-style) | Low RAM, cheap storage | Label-based filtering, Prometheus ecosystem |
| **Vector + ClickHouse** | Columnar DB | SQL | Medium | High-throughput structured logs |
| **Quickwit** | Object storage | Elasticsearch-compatible | Very low | Cost-efficient log search at scale |

**Recommendation for this RAG app**: **Grafana Loki**.
- It integrates natively with Prometheus metrics and Tempo traces in Grafana (the "LGTM" stack).
- It does NOT index log contents, making it far cheaper than Elasticsearch.
- It uses the same labels concept as Prometheus, simplifying operations.
- Self-hostable with a single binary or Docker Compose.

#### Correlation IDs for Request Tracing

```python
# Log output example with correlation IDs
{
  "timestamp": "2026-05-15T14:32:01Z",
  "level": "info",
  "logger": "rag.document_processor",
  "event": "docling_complete",
  "request_id": "req_abc123",
  "session_id": "sess_xyz789",
  "doc_count": 15,
  "duration_ms": 12450
}
```

In Loki/Grafana, query:
```logql
{app="rag-app"} |= `request_id="req_abc123"`
```

This pulls every log line across Docling, embedding, vector store, and agent layers for a single request.

---

### 6. Performance Profiling

#### `cProfile` for Python Bottlenecks

```bash
# Profile the Reflex backend startup + one upload
python -m cProfile -o profile.stats -m RAG_app.RAG_app

# Analyze
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumtime').print_stats(20)"
```

**Programmatic usage inside a background task**:

```python
import cProfile
import pstats
import io

@rx.event(background=True)
async def start_processing(self):
    pr = cProfile.Profile()
    pr.enable()

    # ... processing ...

    pr.disable()
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumtime")
    ps.print_stats(20)
    logger.info("profiling_result", stats=s.getvalue()[:2000])
```

#### Memory Profiling

```bash
pip install memory_profiler
```

```python
from memory_profiler import profile

@profile
def process_uploaded_files(self, file_data):
    # ... docling processing ...
    pass
```

Run:
```bash
python -m memory_profiler RAG_app/core/document_processor.py
```

#### `tracemalloc` (Production-Safe)

```python
import tracemalloc

tracemalloc.start()

# ... run workload ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")
for stat in top_stats[:10]:
    print(stat)
```

#### Reflex-Specific Profiling Tips

| Tip | Why |
|-----|-----|
| Profile `async with self:` blocks | State serialization is expensive for large lists/dicts |
| Measure `process_progress` update frequency | Every `async with self:` triggers a WebSocket round-trip; batch updates |
| Check `rx.UploadFile.read()` memory | Large PDFs (100MB+) read entirely into RAM; stream or save to disk |
| Profile Chroma `upsert` | In-memory SQLite can be slow for >10k chunks; batch insert |
| Watch for state bloat | Do not store `Document` objects, PIL images, or vector arrays in `rx.State` |
| Use `yield` strategically | Yield every N chunks, not every chunk, to reduce frontend thrash |

---

## Recommended Stack for This RAG App

### Phase 1: Single-Node Deployment (Current)

| Concern | Technology | Integration Point |
|---------|------------|-------------------|
| **Concurrency** | `ProcessPoolExecutor` + `asyncio` | `upload_state.py` offload Docling |
| **Metrics** | `prometheus-client` | `/metrics` endpoint in `health.py` |
| **Dashboards** | Grafana (local Docker) | Prometheus data source |
| **Logs** | `structlog` (JSON) + Loki (Docker) | `logging_config.py` → Promtail → Loki |
| **Traces** | OpenTelemetry SDK + Jaeger (Docker) | Custom spans in pipeline |
| **Health** | FastAPI router | `/health/live`, `/health/ready` |

### Phase 2: Multi-Node / Production Scale

| Concern | Upgrade |
|---------|---------|
| **Concurrency** | Migrate `ProcessPoolExecutor` → **RQ** + Redis |
| **Worker Isolation** | RQ workers in separate containers with `--max-jobs 10` |
| **Metrics** | Keep `prometheus-client`; scrape via Prometheus federation |
| **Logs** | Centralized Loki cluster with object storage backend (S3/MinIO) |
| **Traces** | OpenTelemetry Collector sidecar → Tempo |
| **Alerting** | Prometheus Alertmanager → Slack/PagerDuty |

### Architecture Diagram (Phase 2)

```
┌─────────────┐      WebSocket/SSE      ┌─────────────────────────────────┐
│   Browser   │ ◄─────────────────────► │      Reflex App Servers         │
│  (React)    │                         │  ┌─────────┐  ┌─────────┐       │
└─────────────┘                         │  │ Reflex  │  │ Reflex  │ ...   │
                                        │  │ App #1  │  │ App #2  │       │
                                        │  └───┬─────┘  └────┬────┘       │
                                        │      │             │            │
                                        │      ▼             ▼            │
                                        │  ┌─────────────────────────┐    │
                                        │  │  Redis (Session + RQ)   │    │
                                        │  └─────────────────────────┘    │
                                        └─────────────────────────────────┘
                                                     │
                                                     │ RQ Jobs
                                                     ▼
                                        ┌─────────────────────────────────┐
                                        │      RQ Worker Pool             │
                                        │  ┌─────────┐  ┌─────────┐       │
                                        │  │ Worker  │  │ Worker  │ ...   │
                                        │  │ Docling │  │ Docling │       │
                                        │  └───┬─────┘  └────┬────┘       │
                                        └──────┼─────────────┼─────────────┘
                                               │             │
                                               ▼             ▼
                                        ┌─────────────────────────────────┐
                                        │   Chroma (Persistent) / PGVector│
                                        └─────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         Observability Stack (LGTM)                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  Grafana    │◄───│  Prometheus │    │    Loki     │    │    Tempo    │  │
│  │  (UI)       │    │  (Metrics)  │    │   (Logs)    │    │  (Traces)   │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         ▲                  ▲                  ▲                  ▲          │
│         │ scrape           │ Promtail         │ OTLP             │ OTLP     │
│         │                  │ push             │ Collector        │ Collector│
└─────────┼──────────────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │                  │
          └──────────────────┴──────────────────┴──────────────────┘
                                    Reflex App
```

---

## Summary & Action Items

### Immediate (This Sprint)
1. **Offload Docling** to `ProcessPoolExecutor` in `upload_state.py` to fix event loop blocking.
2. **Add correlation IDs** to `logging_config.py` using `structlog.contextvars`.
3. **Expose `/health/ready` and `/metrics`** via a FastAPI router.

### Short-Term (Next Sprint)
4. **Instrument pipeline stages** with OpenTelemetry spans (Docling, embedding, search).
5. **Deploy Prometheus + Grafana** locally via Docker Compose.
6. **Add custom Prometheus metrics** for documents processed, tokens consumed, and processing duration.

### Long-Term (Scaling)
7. **Replace `ProcessPoolExecutor` with RQ** when moving to multiple app servers.
8. **Centralize logs** with Loki and Promtail.
9. **Add alerting rules** in Prometheus for error rates, memory leaks, and API latency.
10. **Implement circuit breakers** for Gemini API calls (resilience pattern).

---

## References

- [Reflex Background Events](https://reflex.dev/docs/events/background-events/)
- [Python asyncio — Event Loop](https://docs.python.org/3/library/asyncio-eventloop.html)
- [RQ Documentation](https://python-rq.org/)
- [Celery Documentation](https://docs.celeryq.dev/en/stable/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [OpenTelemetry FastAPI Instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html)
- [Prometheus Metric Types](https://prometheus.io/docs/concepts/metric_types/)
- [Grafana Loki](https://grafana.com/oss/loki/)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
