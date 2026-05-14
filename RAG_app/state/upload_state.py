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
        self.current_task_message = f"✓ {len(uploaded_info)} file(s) ready. Click 'Process & Vectorize' to analyze."
        logger.info("upload_complete", file_count=len(file_data), total_mb=round(total_size_mb, 2), session_id=self.session_id)

    @rx.event(background=True)
    async def start_processing(self):
        """
        Background task that does the heavy lifting:
        Docling → Chunking → Vectorization → Agent creation.
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
            self.current_task_message = "Processing documents with Docling..."

        try:
            file_data = _upload_buffers.pop(self.session_id, [])
            logger.info("processing_file_data_retrieved", file_count=len(file_data), session_id=self.session_id)

            processor = DocumentProcessor()
            documents, docling_docs = processor.process_uploaded_files(file_data)
            logger.info("docling_complete", doc_count=len(documents), session_id=self.session_id)

            async with self:
                self.process_progress = 40
                self.current_task_message = f"Processed {len(documents)} pages. Creating vector store..."

            if not documents:
                async with self:
                    self.is_processing = False
                    self.current_task_message = "No documents were successfully processed."
                logger.warning("processing_no_documents", session_id=self.session_id)
                return

            total_pages = sum(doc.metadata.get("total_pages", 0) for doc in documents)

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

            search_tool = create_search_tool(vectorstore)
            agent = create_documentation_agent([search_tool])
            registry.set(self.session_id, "agent", agent)
            logger.info("agent_created", session_id=self.session_id)

            async with self:
                self.processed_files = [f["name"] for f in self.uploaded_files]
                self.is_processing = False
                self.process_progress = 100
                self.current_task_message = "✅ Documents processed successfully! Ready to chat."
                self.document_stats["vector_count"] = len(chunks)
                logger.info("processing_complete", session_id=self.session_id, total_chunks=len(chunks))

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
