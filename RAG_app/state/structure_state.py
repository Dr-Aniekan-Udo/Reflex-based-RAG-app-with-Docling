import reflex as rx
from typing import List, Dict, Any

from ..core.session_registry import get_registry
from ..core.structure import DocumentStructureVisualizer
from ..core.logging_config import logger
from .base_state import BaseState


class StructureState(BaseState):
    """State for document structure visualization."""

    selected_document: str = ""
    available_documents: List[str] = []
    current_summary: Dict[str, Any] = {}
    current_hierarchy_html: str = ""
    current_tables_html: List[Dict[str, Any]] = []
    current_pictures: List[Dict[str, Any]] = []

    @rx.var
    def text_types_list(self) -> List[tuple]:
        text_types = self.current_summary.get("text_types", {})
        return sorted(text_types.items(), key=lambda x: -x[1])

    @rx.event
    async def load_available_documents(self):
        logger.info("load_available_documents_called", session_id=self.session_id)
        registry = get_registry()
        entry = registry.get(self.session_id)
        docling_docs = entry.get("docling_docs", [])

        if not docling_docs:
            self.available_documents = []
            logger.info("no_docling_docs_found", session_id=self.session_id)
            return

        unique_files = set()
        for batch in docling_docs:
            filename = batch['filename']
            if " (Pages" in filename:
                base_name = filename.split(" (Pages")[0]
            else:
                base_name = filename
            unique_files.add(base_name)

        self.available_documents = sorted(list(unique_files))
        logger.info("available_documents_loaded", count=len(self.available_documents), documents=self.available_documents, session_id=self.session_id)

        if self.available_documents and not self.selected_document:
            self.selected_document = self.available_documents[0]
            return StructureState.load_document_structure()

    @rx.event
    def select_document(self, filename: str):
        logger.info("select_document", filename=filename, session_id=self.session_id)
        self.selected_document = filename
        return StructureState.load_document_structure()

    @rx.event
    async def load_document_structure(self):
        logger.info("load_document_structure_called", document=self.selected_document, session_id=self.session_id)
        if not self.selected_document:
            logger.warning("load_document_structure_no_selection", session_id=self.session_id)
            return

        registry = get_registry()
        entry = registry.get(self.session_id)
        docling_docs = entry.get("docling_docs", [])

        selected_batches = []
        for batch in docling_docs:
            full_name = batch['filename']
            if " (Pages" in full_name:
                base_name = full_name.split(" (Pages")[0]
            else:
                base_name = full_name

            if base_name == self.selected_document:
                selected_batches.append(batch)

        if not selected_batches:
            logger.warning("no_batches_found", document=self.selected_document, session_id=self.session_id)
            return

        logger.info("structure_batches_found", batch_count=len(selected_batches), session_id=self.session_id)
        visualizer = DocumentStructureVisualizer(selected_batches)
        self.current_summary = visualizer.get_document_summary()
        self.current_hierarchy_html = visualizer.get_hierarchy_html()
        self.current_tables_html = visualizer.get_tables_html()
        self.current_pictures = visualizer.get_pictures_info()
        logger.info("structure_loaded", session_id=self.session_id, summary=self.current_summary)
