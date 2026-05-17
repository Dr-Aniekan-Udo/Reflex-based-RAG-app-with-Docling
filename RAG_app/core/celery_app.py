"""
Celery application configuration with Redis broker.
"""
import os
import logging
from io import BytesIO
from dotenv import load_dotenv
from celery import Celery
from celery.signals import worker_ready

# Load .env so Celery workers pick up GOOGLE_API_KEY, etc.
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "rag_app",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["RAG_app.core.celery_tasks"],
)

celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_track_started=True,
    task_time_limit=600,          # Hard limit: 10 minutes
    task_soft_time_limit=480,     # Soft limit: 8 minutes (warning before kill)

    # Worker behavior
    worker_prefetch_multiplier=1,  # Only fetch 1 task at a time
    worker_max_tasks_per_child=5,  # Restart after 5 tasks (balance: model cache vs memory leak)

    # Rate limiting
    task_default_rate_limit="2/m",  # Max 2 tasks per minute globally

    # Retries
    task_default_retry_delay=30,
    task_max_retries=3,

    # Result backend
    result_backend=REDIS_URL,
    result_expires=3600,           # Results expire after 1 hour
    result_extended=False,         # Disabled: task args contain bytes (PDF data) which break JSON serialization

    # Broker connection
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_connection_timeout=30,

    # Visibility timeout (must exceed longest task time)
    broker_transport_options={
        "visibility_timeout": 7200,  # 2 hours
    },
)

# Suppress Celery task result logging to prevent document content leaks
celery_trace_logger = logging.getLogger("celery.app.trace")
celery_trace_logger.setLevel(logging.WARNING)


@worker_ready.connect
def prewarm_docling_models(sender, **kwargs):
    """
    Pre-warm Docling models when the worker starts.
    This avoids the 5-15s model load delay on the first real document.
    """
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.document import DocumentStream

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = 2.0

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )

        # Run a dummy conversion on a minimal blank PDF to force model loading
        # A valid minimal PDF is just a few hundred bytes
        blank_pdf = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
            b"0000000058 00000 n\n0000000115 00000 n\n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n177\n%%EOF\n"
        )
        source = DocumentStream(name="warmup.pdf", stream=BytesIO(blank_pdf))
        result = converter.convert(source)
        _ = result.document.export_to_markdown()

        logging.getLogger(__name__).info("Docling models pre-warmed successfully")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Docling pre-warm failed (will load on first doc): {e}")
