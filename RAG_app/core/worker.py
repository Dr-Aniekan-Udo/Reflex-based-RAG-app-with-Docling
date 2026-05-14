"""
CPU-bound document processing worker for ProcessPoolExecutor.
No Reflex imports. Runs in a separate process.
"""
from typing import List, Tuple, Dict, Any
from collections import defaultdict


def process_documents(file_data: List[Tuple[str, bytes]]) -> Dict[str, Any]:
    """
    Process uploaded documents with Docling in a worker process.

    Returns fully serializable data:
    - chunks: List of dicts with page_content and metadata
    - doc_structures: Dict mapping filename -> structure data
    - available_documents: List of unique document names
    - stats: total_pages, total_chunks
    - success/error status
    """
    from .document_processor import DocumentProcessor
    from .vector_store import VectorStoreManager
    from .structure import DocumentStructureVisualizer

    processor = DocumentProcessor()
    documents, docling_docs = processor.process_uploaded_files(file_data)

    if not documents:
        return {
            "success": False,
            "error": "No documents were successfully processed",
            "chunks": [],
            "doc_structures": {},
            "available_documents": [],
            "stats": {"total_pages": 0, "total_chunks": 0},
        }

    # Chunk documents
    vs_manager = VectorStoreManager()
    chunks = vs_manager.chunk_documents(documents)

    # Serialize chunks for IPC
    serialized_chunks = [
        {"page_content": c.page_content, "metadata": c.metadata}
        for c in chunks
    ]

    # Build per-document structures
    doc_groups = defaultdict(list)
    for batch in docling_docs:
        full_name = batch["filename"]
        if " (Pages" in full_name:
            base_name = full_name.split(" (Pages")[0]
        else:
            base_name = full_name
        doc_groups[base_name].append(batch)

    doc_structures = {}
    available_documents = []
    for base_name, batches in sorted(doc_groups.items()):
        available_documents.append(base_name)
        vis = DocumentStructureVisualizer(batches)
        doc_structures[base_name] = vis.export_full_structure()

    total_pages = sum(doc.metadata.get("total_pages", 0) for doc in documents)

    return {
        "success": True,
        "chunks": serialized_chunks,
        "doc_structures": doc_structures,
        "available_documents": available_documents,
        "stats": {
            "total_pages": total_pages,
            "total_chunks": len(chunks),
        },
    }
