import reflex as rx
from typing import List, Dict, Any

from ..core.session_registry import get_registry
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
    def clear_structure(self):
        """Reset all document analysis state when documents are cleared."""
        self.selected_document = ""
        self.available_documents = []
        self.current_summary = {}
        self.current_hierarchy_html = ""
        self.current_tables_html = []
        self.current_pictures = []

    @rx.event
    async def load_available_documents(self):
        logger.info("load_available_documents_called", session_id=self.session_id)
        registry = get_registry()
        entry = registry.get(self.session_id)
        doc_structures = entry.get("doc_structures", {})

        if not doc_structures:
            self.available_documents = []
            logger.info("no_doc_structures_found", session_id=self.session_id)
            return

        self.available_documents = sorted(list(doc_structures.keys()))
        logger.info(
            "available_documents_loaded",
            count=len(self.available_documents),
            documents=self.available_documents,
            session_id=self.session_id,
        )

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
        doc_structures = entry.get("doc_structures", {})

        doc_data = doc_structures.get(self.selected_document, {})
        if not doc_data:
            logger.warning("no_structure_data_found", document=self.selected_document, session_id=self.session_id)
            return

        self.current_summary = doc_data.get("summary", {})
        self.current_hierarchy_html = doc_data.get("hierarchy_html", "")
        self.current_tables_html = doc_data.get("tables_html", [])
        self.current_pictures = doc_data.get("pictures", [])
        logger.info("structure_loaded", session_id=self.session_id, summary=self.current_summary)
