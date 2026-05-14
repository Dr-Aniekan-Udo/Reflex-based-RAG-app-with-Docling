import reflex as rx
import asyncio
from typing import List, Dict, Tuple, Any

from ..core.session_registry import get_registry
from ..core.document_processor import DocumentProcessor
from ..core.vector_store import VectorStoreManager
from ..core.tools import create_search_tool
from ..core.agent import create_documentation_agent
from ..core.logging_config import logger
from .base_state import BaseState


# Module-level buffer for uploaded bytes.
_upload_buffers: Dict[str, List[Tuple[str, bytes]]] = {}


class UploadState(BaseState):
    """State management for file ingestion and vectorization."""

    is_processing: bool = False
    process_progress: int = 0
    current_task_message: str = "Ready to upload documents"
    uploaded_files: List[str] = []
    processed_files: List[str] = []
    document_stats: Dict[str, Any] = {
        "total_files": 0,
        "total_size_mb": 0.0,
        "total_pages": 0,
        "vector_count": 0,
    }

    @rx.event(background=True)
    async def process_documents(self, files: List[rx.UploadFile]):
        """
        Combined handler: reads uploaded files and immediately processes them.
        This replaces the broken two-step (upload → process) flow.
        """
        logger.info("process_documents_called", file_count=len(files) if files else 0, session_id=self.session_id)

        async with self:
            if not files:
                self.current_task_message = "No files selected. Please drop files first."
                logger.warning("process_documents_no_files", session_id=self.session_id)
                return
            self.is_processing = True
            self.process_progress = 5
            self.current_task_message = "Reading files into memory..."

        # Phase 0: Read files into memory buffer
        try:
            file_data: List[Tuple[str, bytes]] = []
            uploaded_names: List[str] = []
            total_size_mb = 0.0

            for file in files:
                try:
                    upload_data = await file.read()
                    file_data.append((file.filename, upload_data))
                    uploaded_names.append(file.filename)
                    file_size_mb = len(upload_data) / (1024 * 1024)
                    total_size_mb += file_size_mb
                    logger.info("file_read", filename=file.filename, size_mb=round(file_size_mb, 2), session_id=self.session_id)
                except Exception as e:
                    logger.error("file_read_error", filename=file.filename, error=str(e), session_id=self.session_id)
                    continue

            global _upload_buffers
            _upload_buffers[self.session_id] = file_data

            async with self:
                self.uploaded_files = uploaded_names
                self.document_stats["total_files"] = len(uploaded_names)
                self.document_stats["total_size_mb"] = round(total_size_mb, 2)
                self.process_progress = 15
                self.current_task_message = f"✓ {len(uploaded_names)} file(s) read. Processing with Docling..."
                logger.info("files_buffered", count=len(file_data), session_id=self.session_id)

        except Exception as e:
            logger.error("buffer_error", error=str(e), session_id=self.session_id)
            async with self:
                self.is_processing = False
                self.current_task_message = f"Error reading files: {str(e)}"
            return

        # Phase 1: Docling processing
        try:
            registry = get_registry()
            processor = DocumentProcessor()
            documents, docling_docs = processor.process_uploaded_files(file_data)
            logger.info("docling_complete", doc_count=len(documents), session_id=self.session_id)

            async with self:
                self.process_progress = 50
                self.current_task_message = f"Processed {len(documents)} pages. Creating vector store..."

            if not documents:
                async with self:
                    self.is_processing = False
                    self.current_task_message = "No documents were successfully processed."
                logger.warning("no_documents", session_id=self.session_id)
                return

            total_pages = sum(doc.metadata.get("total_pages", 0) for doc in documents)

            # Phase 2: Vector store
            vs_manager = VectorStoreManager()
            chunks = vs_manager.chunk_documents(documents)
            vectorstore = vs_manager.create_vectorstore(chunks)
            logger.info("vectorstore_created", chunk_count=len(chunks), session_id=self.session_id)

            registry.set(self.session_id, "vectorstore", vectorstore)
            registry.set(self.session_id, "docling_docs", docling_docs)

            async with self:
                self.document_stats["total_pages"] = total_pages
                self.process_progress = 80
                self.current_task_message = "Initializing AI agent..."

            # Phase 3: Agent
            search_tool = create_search_tool(vectorstore)
            agent = create_documentation_agent([search_tool])
            registry.set(self.session_id, "agent", agent)
            logger.info("agent_created", session_id=self.session_id)

            async with self:
                self.processed_files = list(self.uploaded_files)
                self.is_processing = False
                self.process_progress = 100
                self.current_task_message = "✅ Documents processed successfully! Ready to chat."
                self.document_stats["vector_count"] = len(chunks)
                logger.info("process_complete", session_id=self.session_id, total_chunks=len(chunks))

        except Exception as e:
            logger.error("process_error", error=str(e), session_id=self.session_id, exc_info=True)
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
