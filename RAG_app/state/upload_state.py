import asyncio
import reflex as rx
from typing import List, Dict, Tuple, Any

from langchain_core.documents import Document

from ..core.session_registry import get_registry
from ..core.document_processor import DocumentProcessor
from ..core.vector_store import VectorStoreManager
from ..core.tools import create_search_tool
from ..core.agent import create_documentation_agent
from ..core.logging_config import logger
from ..core.executor import get_executor
from ..core.worker import process_documents
from .base_state import BaseState
from .structure_state import StructureState


# Module-level buffer for uploaded bytes.
_upload_buffers: Dict[str, List[Tuple[str, bytes]]] = {}


class UploadState(BaseState):
    """State management for file ingestion and vectorization."""

    is_processing: bool = False
    process_progress: int = 0
    current_task_message: str = "Ready to upload documents"
    uploaded_files: List[Dict[str, Any]] = []
    processed_files: List[str] = []
    document_stats: Dict[str, Any] = {
        "total_files": 0,
        "total_size_mb": 0.0,
        "total_pages": 0,
        "vector_count": 0,
    }

    @rx.event
    async def handle_upload(self, files: List[rx.UploadFile]):
        """
        Normal event handler that reads uploaded files into memory buffer.
        Called automatically when files are dropped/selected.
        """
        logger.info("handle_upload_called", file_count=len(files) if files else 0, session_id=self.session_id)

        if not files:
            self.current_task_message = "No files selected. Please drop files first."
            logger.warning("handle_upload_no_files", session_id=self.session_id)
            return

        self.current_task_message = "Reading files into memory..."
        file_data: List[Tuple[str, bytes]] = []
        uploaded_info: List[Dict[str, Any]] = []
        total_size_mb = 0.0

        for file in files:
            try:
                upload_data = await file.read()
                file_data.append((file.filename, upload_data))
                file_size_mb = len(upload_data) / (1024 * 1024)
                uploaded_info.append({
                    "name": file.filename,
                    "size_mb": round(file_size_mb, 2)
                })
                total_size_mb += file_size_mb
                logger.info("file_read", filename=file.filename, size_mb=round(file_size_mb, 2), session_id=self.session_id)
            except Exception as e:
                logger.error("file_read_error", filename=file.filename, error=str(e), session_id=self.session_id)
                continue

        global _upload_buffers
        _upload_buffers[self.session_id] = file_data

        self.uploaded_files = uploaded_info
        self.document_stats["total_files"] = len(uploaded_info)
        self.document_stats["total_size_mb"] = round(total_size_mb, 2)
        self.current_task_message = f"✓ {len(uploaded_info)} file(s) ready. Click 'Process' to analyze."
        logger.info("upload_complete", file_count=len(file_data), total_mb=round(total_size_mb, 2), session_id=self.session_id)

    @rx.event(background=True)
    async def start_processing(self):
        """
        Background task that orchestrates document processing.
        CPU-bound Docling work is offloaded to ProcessPoolExecutor.
        I/O-bound embedding runs in ThreadPoolExecutor.
        """
        global _upload_buffers
        registry = get_registry()

        logger.info("start_processing_called", session_id=self.session_id)

        async with self:
            if not _upload_buffers.get(self.session_id):
                self.current_task_message = "No files to process. Please upload documents first."
                logger.warning("processing_no_files", session_id=self.session_id)
                return
            self.is_processing = True
            self.process_progress = 10
            self.current_task_message = "Processing documents with Docling (CPU worker)..."

        try:
            file_data = _upload_buffers.pop(self.session_id, [])
            logger.info("processing_file_data_retrieved", file_count=len(file_data), session_id=self.session_id)

            # ─── Offload CPU-bound Docling to worker process ───
            result = None
            try:
                executor = get_executor()
                future = executor.submit(process_documents, file_data)
                result = await asyncio.wrap_future(future)
                logger.info("worker_complete", success=result.get("success"), session_id=self.session_id)
            except Exception as pool_err:
                logger.error("process_pool_failed", error=str(pool_err), fallback="sync", session_id=self.session_id)
                # Fallback: run synchronously (blocks event loop but ensures functionality)
                result = process_documents(file_data)

            if not result.get("success"):
                error_msg = result.get("error", "Unknown processing error")
                logger.error("processing_failed", error=error_msg, session_id=self.session_id)
                async with self:
                    self.is_processing = False
                    self.current_task_message = f"Error: {error_msg}"
                return

            chunks_data = result["chunks"]
            doc_structures = result["doc_structures"]
            available_documents = result["available_documents"]
            stats = result["stats"]

            async with self:
                self.process_progress = 50
                self.current_task_message = f"Processed {stats['total_pages']} pages. Creating embeddings..."

            if not chunks_data:
                async with self:
                    self.is_processing = False
                    self.current_task_message = "No documents were successfully processed."
                logger.warning("processing_no_chunks", session_id=self.session_id)
                return

            # ─── Reconstruct Document objects ───
            chunk_docs = [
                Document(page_content=c["page_content"], metadata=c["metadata"])
                for c in chunks_data
            ]

            # ─── Create vector store (embedding + Chroma) in thread pool ───
            vs_manager = VectorStoreManager()
            try:
                vectorstore = await asyncio.to_thread(
                    vs_manager.create_vectorstore, chunk_docs
                )
                logger.info("vectorstore_created", chunk_count=len(chunk_docs), session_id=self.session_id)
            except Exception as vs_err:
                logger.error("vectorstore_creation_failed", error=str(vs_err), session_id=self.session_id)
                async with self:
                    self.is_processing = False
                    self.current_task_message = f"Vector store error: {str(vs_err)}"
                return

            # Store in registry
            registry.set(self.session_id, "vectorstore", vectorstore)
            registry.set(self.session_id, "doc_structures", doc_structures)

            async with self:
                self.document_stats["total_pages"] = stats["total_pages"]
                self.process_progress = 80
                self.current_task_message = "Initializing AI agent..."

            # ─── Create agent ───
            search_tool = create_search_tool(vectorstore)
            agent = create_documentation_agent([search_tool])
            registry.set(self.session_id, "agent", agent)
            logger.info("agent_created", session_id=self.session_id)

            async with self:
                self.processed_files = [f["name"] for f in self.uploaded_files]
                self.is_processing = False
                self.process_progress = 100
                self.current_task_message = "✅ Documents processed successfully! Ready to chat."
                self.document_stats["vector_count"] = stats["total_chunks"]
                logger.info("processing_complete", session_id=self.session_id, total_chunks=len(chunk_docs))

        except Exception as e:
            logger.error("processing_error", error=str(e), session_id=self.session_id, exc_info=True)
            async with self:
                self.is_processing = False
                self.current_task_message = f"Error: {str(e)}"

    @rx.event
    def clear_documents(self):
        logger.info("clear_documents", session_id=self.session_id)
        registry = get_registry()
        registry.clear(self.session_id)
        global _upload_buffers
        if self.session_id in _upload_buffers:
            del _upload_buffers[self.session_id]

        self.uploaded_files = []
        self.processed_files = []
        self.document_stats = {
            "total_files": 0,
            "total_size_mb": 0.0,
            "total_pages": 0,
            "vector_count": 0,
        }
        self.process_progress = 0
        self.current_task_message = "Ready to upload documents"
        self.is_processing = False
        return StructureState.clear_structure()
