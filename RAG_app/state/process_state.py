"""
Process state for document upload and vectorization.
Handles heavy, non-blocking operations with progress tracking.
Files are kept in memory temporarily and cleaned up after processing.
"""

import reflex as rx
import asyncio
from typing import List, Dict, Tuple, Any

from ..services import get_vector_store, get_llm_service


class ProcessState(rx.State):
    """State management for file ingestion and vectorization"""

    # Upload status
    is_uploading: bool = False
    is_processing: bool = False

    # Progress tracking (0-100)
    upload_progress: int = 0
    process_progress: int = 0

    # Status messages
    current_task_message: str = "Ready to upload documents"

    # File tracking - separated by stage
    selected_files: List[str] = []  # Files selected but not yet uploaded
    uploaded_files: List[str] = []  # Files uploaded and ready to process
    processed_files: List[str] = []  # Files successfully processed

    # Document statistics
    document_stats: Dict[str, float] = {
        "total_files": 0,
        "total_size_mb": 0.0,
        "total_pages": 0,
        "vector_count": 0,
    }

    # Store docling docs for visualization
    docling_docs: List[Dict[str, Any]] = []

    # Internal storage for uploaded binary data (in memory)
    _uploaded_data: List[Tuple[str, bytes]] = []

    @rx.event
    async def handle_file_selection(self, files: List[rx.UploadFile]):
        """
        Handle file selection - just show what user selected.
        This runs immediately when files are chosen.
        """
        if not files:
            self.selected_files = []
            return

        # Extract just the filenames to show in selection buffer
        self.selected_files = [file.filename for file in files]
        self.current_task_message = f"{len(files)} file(s) selected - click 'Upload Files' to proceed"

    @rx.event
    async def handle_upload(self, files: List[rx.UploadFile]):
        """
        Handle file upload - read files into memory.
        Does NOT save to disk, keeps everything in memory.
        """
        if not files:
            return

        self.is_uploading = True
        self.upload_progress = 0
        self.current_task_message = "Starting upload..."

        total_files = len(files)
        uploaded_data: List[Tuple[str, bytes]] = []
        uploaded_names: List[str] = []

        for idx, file in enumerate(files):
            try:
                # Read file into memory (bytes)
                upload_data = await file.read()
                
                # Store in memory - NO disk writes
                uploaded_data.append((file.filename, upload_data))
                uploaded_names.append(file.filename)

                # Update stats
                file_size_mb = len(upload_data) / (1024 * 1024)
                self.document_stats["total_files"] += 1
                self.document_stats["total_size_mb"] = round(
                    self.document_stats["total_size_mb"] + file_size_mb, 2
                )

                # Update progress
                self.upload_progress = int(((idx + 1) / total_files) * 100)
                self.current_task_message = f"Uploaded {file.filename} to memory"

                # Let UI breathe
                await asyncio.sleep(0.05)

            except Exception as e:
                print(f"Error uploading {file.filename}: {e}")
                self.current_task_message = f"Error uploading {file.filename}"

        self.is_uploading = False
        self.uploaded_files = uploaded_names
        self.selected_files = []  # Clear selection buffer
        self.current_task_message = f"✓ {len(uploaded_names)} file(s) uploaded to memory. Ready to process."

        # Store for processing (in memory)
        self._uploaded_data = uploaded_data

    @rx.event(background=True)
    async def start_vectorization(self):
        """
        Background task to process documents and create vector store.
        Files are processed from memory, then cleaned up.
        """

        # Lock state first
        async with self:
            if not self._uploaded_data:
                self.current_task_message = "No files to process. Please upload documents first."
                return

            self.is_processing = True
            self.process_progress = 0
            self.current_task_message = "Initializing document processor..."

        try:
            vector_store = get_vector_store()
            llm_service = get_llm_service()

            # Phase 1: Process documents (from memory)
            async with self:
                self.current_task_message = "Processing documents with Docling..."
                self.process_progress = 10

            documents, docling_docs, success_count, error_count = await vector_store.process_documents(
                self._uploaded_data
            )

            async with self:
                self.docling_docs = docling_docs or []
                self.process_progress = 40
                self.current_task_message = f"Processed {success_count} files. Creating vector store..."

            if not documents:
                async with self:
                    self.is_processing = False
                    self.current_task_message = "No documents were successfully processed."
                return

            # Page count
            total_pages = sum(doc.metadata.get("total_pages", 0) for doc in documents)
            async with self:
                self.document_stats["total_pages"] = total_pages
                self.process_progress = 60
                self.current_task_message = "Chunking and embedding documents..."

            # Phase 2: Vector store
            success = await vector_store.create_vectorstore(documents)

            if not success:
                async with self:
                    self.is_processing = False
                    self.current_task_message = "Error creating vector store."
                return

            async with self:
                self.process_progress = 80
                self.current_task_message = "Initializing AI agent..."

            # Phase 3: Agent
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, llm_service.create_agent)

            # Final - mark files as processed
            async with self:
                self.processed_files = list(self.uploaded_files)
                self.is_processing = False
                self.process_progress = 100
                self.current_task_message = "✅ Documents processed successfully! Ready to chat."
                self.document_stats["vector_count"] = len(documents) * 1536

                # Clean up memory - files are no longer needed
                self._uploaded_data = []

        except Exception as e:
            print(f"Vectorization error: {e}")
            async with self:
                self.is_processing = False
                self.current_task_message = f"Error: {str(e)}"

    @rx.event
    def clear_documents(self):
        """Clear all uploaded documents and reset"""

        vector_store = get_vector_store()
        llm_service = get_llm_service()

        vector_store.reset()
        llm_service.reset()

        self.selected_files = []
        self.uploaded_files = []
        self.processed_files = []
        self.docling_docs = []
        self._uploaded_data = []

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

    @rx.event
    def remove_selected_file(self, filename: str):
        """Remove a file from the selection buffer"""
        if filename in self.selected_files:
            self.selected_files = [f for f in self.selected_files if f != filename]
            if not self.selected_files:
                self.current_task_message = "Ready to upload documents"
