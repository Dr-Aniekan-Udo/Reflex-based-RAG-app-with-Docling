import reflex as rx
import asyncio
import re
from typing import List, Dict, Any
from uuid import uuid4

from langchain_core.documents import Document

from ..core.session_registry import get_registry
from ..core.vector_store import VectorStoreManager
from ..core.tools import create_search_tool
from ..core.agent import create_documentation_agent
from ..core.logging_config import logger
from ..core.celery_app import celery_app
from ..core.celery_tasks import process_document_task
from .base_state import BaseState
from .structure_state import StructureState


# Module-level buffer: doc_id -> bytes
_upload_buffers: Dict[str, bytes] = {}


def _new_document(doc_id: str = "", filename: str = "", size_mb: float = 0.0,
                  status: str = "uploaded", progress: int = 0, message: str = "Ready",
                  pages: int = 0, chunks: int = 0, task_id: str = "", error_message: str = "") -> Dict[str, Any]:
    """Factory for a document dict."""
    return {
        "doc_id": doc_id,
        "filename": filename,
        "size_mb": size_mb,
        "status": status,
        "progress": progress,
        "message": message,
        "pages": pages,
        "chunks": chunks,
        "task_id": task_id,
        "error_message": error_message,
    }


class UploadState(BaseState):
    """State management for per-document ingestion and vectorization."""

    documents: List[Dict[str, Any]] = []
    document_stats: Dict[str, Any] = {
        "total_files": 0,
        "total_size_mb": 0.0,
        "total_pages": 0,
        "vector_count": 0,
    }

    @rx.var
    def is_processing_any(self) -> bool:
        return any(d["status"] == "processing" for d in self.documents)

    @rx.var
    def has_documents(self) -> bool:
        return len(self.documents) > 0

    @rx.var
    def has_completed_documents(self) -> bool:
        return any(d["status"] == "completed" for d in self.documents)

    @rx.event
    async def handle_upload(self, files: List[rx.UploadFile]):
        """Read uploaded files and add them to the document list."""
        logger.info("handle_upload_called", file_count=len(files) if files else 0, session_id=self.session_id)

        if not files:
            return

        for file in files:
            try:
                # Show filename immediately before reading
                doc = _new_document(
                    doc_id=str(uuid4()),
                    filename=file.filename,
                    status="reading",
                    message="Reading file...",
                )
                self.documents.append(doc)

                # Read bytes
                data = await file.read()
                size_mb = len(data) / (1024 * 1024)

                # Update doc info
                doc["size_mb"] = round(size_mb, 2)
                doc["status"] = "uploaded"
                doc["message"] = "Ready to process"

                # Store bytes keyed by doc_id
                global _upload_buffers
                _upload_buffers[doc["doc_id"]] = data

                logger.info("file_added", doc_id=doc["doc_id"], filename=doc["filename"], size_mb=round(size_mb, 2))
            except Exception as e:
                logger.error("file_read_error", filename=file.filename, error=str(e))
                continue

        self._update_stats()

    def _update_stats(self):
        """Recalculate aggregate stats from all documents."""
        self.document_stats = {
            "total_files": len(self.documents),
            "total_size_mb": round(sum(d["size_mb"] for d in self.documents), 2),
            "total_pages": sum(d["pages"] for d in self.documents),
            "vector_count": sum(d["chunks"] for d in self.documents),
        }

    @rx.event
    def process_document(self, doc_id: str):
        """Start processing a single document via Celery."""
        global _upload_buffers
        data = _upload_buffers.get(doc_id)
        if not data:
            logger.warning("process_no_data", doc_id=doc_id)
            return

        doc = self._get_doc(doc_id)
        if not doc or doc["status"] == "processing":
            return

        doc["status"] = "processing"
        doc["progress"] = 5
        doc["message"] = "Queued for processing..."
        doc["error_message"] = ""
        # Reset error log flags on new attempt
        doc["error_logged"] = False
        doc["poll_error_logged"] = False

        try:
            result = process_document_task.delay(data, doc["filename"], doc_id)
            doc["task_id"] = result.id
            logger.info("process_queued", doc_id=doc_id, task_id=result.id, filename=doc["filename"])
        except Exception as e:
            doc["status"] = "error"
            doc["error_message"] = str(e)
            logger.error("process_enqueue_failed", doc_id=doc_id, error=str(e))

    @rx.event(background=True)
    async def poll_document_tasks(self):
        """Background task that polls Celery task status and updates state."""
        while True:
            await asyncio.sleep(2)

            async with self:
                processing_docs = [d for d in self.documents if d["status"] == "processing" and d["task_id"]]
                if not processing_docs:
                    continue

                registry = get_registry()
                vectorstore = registry.get(self.session_id).get("vectorstore")
                doc_structures = registry.get(self.session_id).get("doc_structures", {})
                all_chunks_data = []
                all_available_docs = set()

                for doc in processing_docs:
                    task_id = doc["task_id"]
                    try:
                        result = celery_app.AsyncResult(task_id)
                        state = result.state

                        if state == "PENDING":
                            doc["message"] = "Waiting for worker..."
                        elif state == "STARTED":
                            meta = result.info or {}
                            doc["progress"] = meta.get("progress", 10)
                            doc["message"] = meta.get("message", "Processing...")
                        elif state == "SUCCESS":
                            data = result.result or {}
                            if data.get("success"):
                                doc["status"] = "completed"
                                doc["progress"] = 100
                                doc["message"] = f"Done — {data['stats']['chunks']} chunks"
                                doc["pages"] = data["stats"]["pages"]
                                doc["chunks"] = data["stats"]["chunks"]

                                # Collect chunks for batch vectorstore creation
                                all_chunks_data.extend(data.get("chunks", []))
                                doc_structures.update(data.get("doc_structures", {}))
                                all_available_docs.update(data.get("available_documents", []))
                            else:
                                doc["status"] = "error"
                                doc["error_message"] = data.get("error", "Unknown error")
                                doc["message"] = "Failed"
                                if not doc.get("error_logged"):
                                    logger.error("task_failed", doc_id=doc["doc_id"], error=doc["error_message"])
                                    doc["error_logged"] = True
                        elif state in ("FAILURE", "REVOKED"):
                            doc["status"] = "error"
                            try:
                                exc = getattr(result, 'result', None)
                                if exc is not None:
                                    error_msg = str(exc)
                                    if "Exception(" in error_msg:
                                        match = re.search(r"Exception\((.+?)\)$", error_msg)
                                        if match:
                                            error_msg = match.group(1)
                                    if len(error_msg) > 200:
                                        error_msg = error_msg[:200] + "..."
                                else:
                                    error_msg = "Task failed"
                            except Exception:
                                error_msg = "Task failed"
                            doc["error_message"] = error_msg
                            doc["message"] = "Failed"
                            if not doc.get("error_logged"):
                                logger.error("task_failed", doc_id=doc["doc_id"], error=error_msg)
                                doc["error_logged"] = True

                    except ValueError as ve:
                        # Celery Redis backend corruption: missing exc_type in result metadata
                        # This happens when retry exceptions are stored incorrectly
                        error_text = str(ve)
                        if "Exception information must include" in error_text:
                            doc["status"] = "error"
                            doc["error_message"] = "Task failed (Celery result corrupted)"
                            doc["message"] = "Failed"
                            if not doc.get("error_logged"):
                                logger.error("task_failed_celery_corruption", doc_id=doc["doc_id"], task_id=task_id)
                                doc["error_logged"] = True
                        else:
                            # Other ValueError — log once
                            if not doc.get("poll_error_logged"):
                                logger.error("poll_value_error", doc_id=doc["doc_id"], error=error_text)
                                doc["poll_error_logged"] = True
                    except Exception as e:
                        # Only log unexpected errors once per doc
                        if not doc.get("poll_error_logged"):
                            logger.error("poll_error", doc_id=doc["doc_id"], error=str(e))
                            doc["poll_error_logged"] = True

                # Update vector store with all completed chunks
                if all_chunks_data:
                    chunk_docs = [
                        Document(page_content=c["page_content"], metadata=c["metadata"])
                        for c in all_chunks_data
                    ]
                    vs_manager = VectorStoreManager()
                    if vectorstore is None:
                        vectorstore = vs_manager.create_vectorstore(chunk_docs)
                    else:
                        vs_manager.add_documents(vectorstore, chunk_docs)

                    registry.set(self.session_id, "vectorstore", vectorstore)
                    registry.set(self.session_id, "doc_structures", doc_structures)

                    # Recreate agent
                    search_tool = create_search_tool(vectorstore)
                    agent = create_documentation_agent([search_tool])
                    registry.set(self.session_id, "agent", agent)

                self._update_stats()

    @rx.event
    def stop_processing(self, doc_id: str):
        """Revoke a running Celery task for a document."""
        doc = self._get_doc(doc_id)
        if not doc or not doc["task_id"]:
            return

        try:
            celery_app.control.revoke(doc["task_id"], terminate=True)
            doc["status"] = "stopped"
            doc["message"] = "Stopped by user"
            doc["progress"] = 0
            logger.info("process_stopped", doc_id=doc_id, task_id=doc["task_id"])
        except Exception as e:
            logger.error("stop_failed", doc_id=doc_id, error=str(e))

    @rx.event
    def retry_document(self, doc_id: str):
        """Retry a failed or stopped document."""
        doc = self._get_doc(doc_id)
        if not doc:
            return
        doc["status"] = "uploaded"
        doc["error_message"] = ""
        doc["progress"] = 0
        doc["message"] = "Ready"
        doc["task_id"] = ""
        doc["error_logged"] = False
        doc["poll_error_logged"] = False
        self.process_document(doc_id)

    @rx.event
    def clear_document(self, doc_id: str):
        """Remove a single document and its data."""
        logger.info("clear_document", doc_id=doc_id, session_id=self.session_id)

        global _upload_buffers
        if doc_id in _upload_buffers:
            del _upload_buffers[doc_id]

        # Remove from vector store
        registry = get_registry()
        entry = registry.get(self.session_id)
        vectorstore = entry.get("vectorstore")
        if vectorstore:
            try:
                vectorstore._collection.delete(where={"doc_id": doc_id})
                logger.info("chunks_deleted", doc_id=doc_id)
            except Exception as e:
                logger.warning("chunk_delete_failed", doc_id=doc_id, error=str(e))

        # Remove from state
        self.documents = [d for d in self.documents if d["doc_id"] != doc_id]
        self._update_stats()

        # If no documents left, clear everything
        if not self.documents:
            registry.clear(self.session_id)
            return StructureState.clear_structure()

    @rx.event
    def process_all_documents(self):
        """Queue all uploaded documents for processing."""
        for doc in self.documents:
            if doc["status"] == "uploaded":
                self.process_document(doc["doc_id"])

    @rx.event
    def clear_all_documents(self):
        """Remove all documents and clear all data."""
        logger.info("clear_all_documents", session_id=self.session_id)

        global _upload_buffers
        for doc in self.documents:
            if doc["doc_id"] in _upload_buffers:
                del _upload_buffers[doc["doc_id"]]

        registry = get_registry()
        registry.clear(self.session_id)

        self.documents = []
        self.document_stats = {
            "total_files": 0,
            "total_size_mb": 0.0,
            "total_pages": 0,
            "vector_count": 0,
        }
        return StructureState.clear_structure()

    def _get_doc(self, doc_id: str) -> Dict[str, Any] | None:
        for d in self.documents:
            if d["doc_id"] == doc_id:
                return d
        return None
