"""
Celery tasks for document processing.
CPU-bound work runs in separate worker processes.
"""
import psutil
from typing import Dict, Any
from celery import current_task

from .celery_app import celery_app
from .document_processor import DocumentProcessor
from .vector_store import VectorStoreManager
from .structure import DocumentStructureVisualizer
from .logging_config import logger


@celery_app.task(bind=True)
def process_document_task(self, file_data: bytes, filename: str, doc_id: str) -> Dict[str, Any]:
    """
    Process a single document: Docling → chunking → embedding → vector store.
    Runs in a Celery worker process with full isolation.
    """
    self.update_state(state="STARTED", meta={"progress": 5, "message": "Checking system resources..."})

    # ─── Resource throttling ───
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 85:
            logger.warning("cpu_throttle", cpu=cpu_percent, doc_id=doc_id, filename=filename)
            self.update_state(state="RETRY", meta={"progress": 5, "message": f"CPU at {cpu_percent}%, waiting..."})
            raise self.retry(exc=Exception(f"CPU throttling at {cpu_percent}%"), countdown=30, max_retries=5)
    except Exception as throttle_err:
        if "CPU throttling" not in str(throttle_err):
            logger.warning("cpu_check_failed", error=str(throttle_err), doc_id=doc_id)

    try:
        # ─── Docling processing ───
        self.update_state(state="STARTED", meta={"progress": 10, "message": "Parsing document with Docling..."})
        processor = DocumentProcessor()
        documents, docling_docs = processor.process_uploaded_files([(filename, file_data)])

        if not documents:
            logger.error("docling_no_output", doc_id=doc_id, filename=filename)
            return {
                "success": False,
                "error": "No text content extracted from document",
                "doc_id": doc_id,
                "pages": 0,
                "chunks": 0,
            }

        total_pages = sum(doc.metadata.get("total_pages", 0) for doc in documents)
        self.update_state(state="STARTED", meta={"progress": 40, "message": f"Extracted {total_pages} pages. Chunking..."})

        # ─── Chunking ───
        vs_manager = VectorStoreManager()
        chunks = vs_manager.chunk_documents(documents)
        self.update_state(state="STARTED", meta={"progress": 50, "message": f"Created {len(chunks)} chunks. Embedding..."})

        # ─── Prepare serializable data ───
        serialized_chunks = [
            {"page_content": c.page_content, "metadata": {**c.metadata, "doc_id": doc_id}}
            for c in chunks
        ]

        # ─── Build per-document structure ───
        doc_structures = {}
        if docling_docs:
            base_name = filename
            if " (Pages" in base_name:
                base_name = base_name.split(" (Pages")[0]
            vis = DocumentStructureVisualizer(docling_docs)
            doc_structures[base_name] = vis.export_full_structure()

        self.update_state(state="STARTED", meta={"progress": 70, "message": "Embeddings complete. Indexing..."})

        return {
            "success": True,
            "doc_id": doc_id,
            "chunks": serialized_chunks,
            "doc_structures": doc_structures,
            "available_documents": sorted(doc_structures.keys()),
            "stats": {
                "pages": total_pages,
                "chunks": len(chunks),
            },
        }

    except Exception as e:
        error_str = str(e)
        logger.error("processing_task_failed", error=error_str, doc_id=doc_id, filename=filename, exc_info=True)
        
        # Only retry for transient errors (CPU throttling, network timeouts)
        # Permanent errors (missing API key, invalid config) should fail immediately
        transient_keywords = ["timeout", "connection", "network", "temporarily", "throttle", "rate limit"]
        is_transient = any(kw in error_str.lower() for kw in transient_keywords)
        
        if is_transient:
            self.update_state(state="RETRY", meta={"progress": 0, "message": f"Retrying: {error_str}"})
            raise self.retry(exc=e, countdown=60, max_retries=2)
        else:
            # Permanent error — return failure, don't retry
            self.update_state(state="FAILURE", meta={"progress": 0, "message": f"Error: {error_str}"})
            return {
                "success": False,
                "error": error_str,
                "doc_id": doc_id,
                "pages": 0,
                "chunks": 0,
            }
