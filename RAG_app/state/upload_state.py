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
# NEVER put bytes inside Reflex state — they are not JSON serializable.
_upload_buffers: Dict[str, List[Tuple[str, bytes]]] = {}


class UploadState(BaseState):
    """State management for file ingestion and vectorization."""

    is_uploading: bool = False
    is_processing: bool = False
    upload_progress: int = 0
    process_progress: int = 0
    current_task_message: str = "Ready to upload documents"
    selected_files: List[str] = []
    uploaded_files: List[str] = []
    processed_files: List[str] = []
    document_stats: Dict[str, Any] = {
        "total_files": 0,
        "total_size_mb": 0.0,
        "total_pages": 0,
        "vector_count": 0,
    }

    @rx.event
    async def handle_file_selection(self, files: List[rx.UploadFile]):
        logger.info("handle_file_selection_called", file_count=len(files) if files else 0, session_id=self.session_id)
        if not files:
            self.selected_files = []
            return
        self.selected_files = [file.filename for file in files]
        self.current_task_message = f"{len(files)} file(s) selected - click 'Upload Files' to proceed"
        logger.info("files_selected", filenames=self.selected_files, session_id=self.session_id)

    @rx.event
    async def handle_upload(self, files: List[rx.UploadFile]):
        logger.info("handle_upload_called", file_count=len(files) if files else 0, session_id=self.session_id)
        if not files:
            logger.warning("handle_upload_no_files", session_id=self.session_id)
            return

        self.is_uploading = True
        self.upload_progress = 0
        self.current_task_message = "Starting upload..."

        total_files = len(files)
        uploaded_data: List[Tuple[str, bytes]] = []
        uploaded_names: List[str] = []

        for idx, file in enumerate(files):
            try:
                upload_data = await file.read()
                uploaded_data.append((file.filename, upload_data))
                uploaded_names.append(file.filename)

                file_size_mb = len(upload_data) / (1024 * 1024)
                self.document_stats["total_files"] += 1
                self.document_stats["total_size_mb"] = round(
                    self.document_stats["total_size_mb"] + file_size_mb, 2
                )

                self.upload_progress = int(((idx + 1) / total_files) * 100)
                self.current_task_message = f"Uploaded {file.filename} to memory"
                await asyncio.sleep(0.05)
                logger.info("file_read_into_memory", filename=file.filename, size_mb=round(file_size_mb, 2), session_id=self.session_id)
            except Exception as e:
                logger.error("file_upload_error", filename=file.filename, error=str(e), session_id=self.session_id)
                self.current_task_message = f"Error uploading {file.filename}"

        self.is_uploading = False
        self.uploaded_files = uploaded_names
        self.selected_files = []
        self.current_task_message = f"✓ {len(uploaded_names)} file(s) uploaded to memory. Ready to process."

        # Store bytes outside of Reflex state
        global _upload_buffers
        _upload_buffers[self.session_id] = uploaded_data
        logger.info("upload_buffer_stored", session_id=self.session_id, file_count=len(uploaded_data))

    @rx.event(background=True)
    async def start_vectorization(self):
        global _upload_buffers
        registry = get_registry()

        logger.info("start_vectorization_called", session_id=self.session_id)

        async with self:
            if not _upload_buffers.get(self.session_id):
                self.current_task_message = "No files to process. Please upload documents first."
                logger.warning("vectorization_no_files", session_id=self.session_id)
                return
            self.is_processing = True
            self.process_progress = 0
            self.current_task_message = "Initializing document processor..."

        try:
            file_data = _upload_buffers.pop(self.session_id, [])
            logger.info("vectorization_file_data_retrieved", file_count=len(file_data), session_id=self.session_id)

            # Phase 1: Process documents
            async with self:
                self.current_task_message = "Processing documents with Docling..."
                self.process_progress = 10

            logger.info("docling_processing_started", file_count=len(file_data), session_id=self.session_id)
            processor = DocumentProcessor()
            documents, docling_docs = processor.process_uploaded_files(file_data)
            logger.info("docling_processing_complete", doc_count=len(documents), session_id=self.session_id)

            async with self:
                self.process_progress = 40
                self.current_task_message = f"Processed pages. Creating vector store..."

            if not documents:
                async with self:
                    self.is_processing = False
                    self.current_task_message = "No documents were successfully processed."
                logger.warning("vectorization_no_documents", session_id=self.session_id)
                return

            total_pages = sum(doc.metadata.get("total_pages", 0) for doc in documents)
            async with self:
                self.document_stats["total_pages"] = total_pages
                self.process_progress = 60
                self.current_task_message = "Chunking and embedding documents..."

            # Phase 2: Vector store
            logger.info("vectorstore_creation_started", doc_count=len(documents), session_id=self.session_id)
            vs_manager = VectorStoreManager()
            chunks = vs_manager.chunk_documents(documents)
            vectorstore = vs_manager.create_vectorstore(chunks)
            logger.info("vectorstore_created", chunk_count=len(chunks), session_id=self.session_id)

            registry.set(self.session_id, "vectorstore", vectorstore)
            registry.set(self.session_id, "docling_docs", docling_docs)

            async with self:
                self.process_progress = 80
                self.current_task_message = "Initializing AI agent..."

            # Phase 3: Agent
            logger.info("agent_creation_started", session_id=self.session_id)
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
                logger.info("vectorization_complete", session_id=self.session_id, total_chunks=len(chunks))

        except Exception as e:
            logger.error("vectorization_error", error=str(e), session_id=self.session_id, exc_info=True)
            async with self:
                self.is_processing = False
                self.current_task_message = f"Error: {str(e)}"

    @rx.event
    def clear_documents(self):
        logger.info("clear_documents_called", session_id=self.session_id)
        registry = get_registry()
        registry.clear(self.session_id)
        global _upload_buffers
        if self.session_id in _upload_buffers:
            del _upload_buffers[self.session_id]

        self.selected_files = []
        self.uploaded_files = []
        self.processed_files = []
        self.document_stats = {
            "total_files": 0,
            "total_size_mb": 0.0,
            "total_pages": 0,
            "vector_count": 0,
        }
        self.upload_progress = 0
        self.process_progress = 0
        self.current_task_message = "Ready to upload documents"
        self.is_uploading = False
        self.is_processing = False
        logger.info("documents_cleared", session_id=self.session_id)

    @rx.event
    def remove_selected_file(self, filename: str):
        logger.info("remove_selected_file", filename=filename, session_id=self.session_id)
        if filename in self.selected_files:
            self.selected_files = [f for f in self.selected_files if f != filename]
            if not self.selected_files:
                self.current_task_message = "Ready to upload documents"
