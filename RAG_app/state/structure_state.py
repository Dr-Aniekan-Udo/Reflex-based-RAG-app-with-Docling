import reflex as rx
from typing import List, Dict, Any

from ..core.session_registry import get_registry
from ..core.structure import DocumentStructureVisualizer
from .base_state import BaseState


class StructureState(BaseState):
    """State for document structure visualization."""

    selected_document: str = ""
    available_documents: List[str] = []
    current_summary: Dict[str, Any] = {}
    current_hierarchy: List[Dict[str, Any]] = []
    current_tables: List[Dict[str, Any]] = []
    current_pictures: List[Dict[str, Any]] = []

    @rx.var
    def text_types_list(self) -> List[tuple]:
        text_types = self.current_summary.get("text_types", {})
        return sorted(text_types.items(), key=lambda x: -x[1])

    @rx.event
    async def load_available_documents(self):
        registry = get_registry()
        entry = registry.get(self.session_id)
        docling_docs = entry.get("docling_docs", [])

        if not docling_docs:
            self.available_documents = []
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
        if self.available_documents and not self.selected_document:
            self.selected_document = self.available_documents[0]
            return StructureState.load_document_structure()

    @rx.event
    def select_document(self, filename: str):
        self.selected_document = filename
        return StructureState.load_document_structure()

    @rx.event
    async def load_document_structure(self):
        if not self.selected_document:
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
            return

        visualizer = DocumentStructureVisualizer(selected_batches)
        self.current_summary = visualizer.get_document_summary()
        self.current_hierarchy = visualizer.get_document_hierarchy()
        self.current_tables = visualizer.get_tables_info()
        self.current_pictures = visualizer.get_pictures_info()
