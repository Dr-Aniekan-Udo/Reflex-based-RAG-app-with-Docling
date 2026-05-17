"""
Vector store management for document storage and retrieval.
Synchronous; the caller (Reflex background task) is responsible for threading.

Uses GeminiEmbedder (google-genai SDK) to bypass the langchain-google-genai
batch embedding bug (Issue #1704).
"""
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from .embeddings import GeminiEmbedder


class VectorStoreManager:
    """Manages document chunking, embedding, and vector storage."""

    def __init__(self):
        self.embedder = GeminiEmbedder()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=len,
        )

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        print(f"✂️ Chunking {len(documents)} documents...")
        chunks = self.text_splitter.split_documents(documents)
        # Filter out empty/whitespace-only chunks to prevent embedding length mismatch
        chunks = [c for c in chunks if c.page_content and c.page_content.strip()]
        print(f"✅ Created {len(chunks)} chunks")
        return chunks

    def create_vectorstore(self, chunks: List[Document]) -> Chroma:
        print(f"🔢 Creating vector store with {len(chunks)} chunks...")

        texts = [c.page_content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = [str(i) for i in range(len(chunks))]

        embeddings = self.embedder.embed_documents(texts)

        # Create empty Chroma instance.
        # We pass a lightweight embed_query wrapper so similarity_search works
        # for query embedding later.
        vectorstore = Chroma(
            embedding_function=self.embedder,
            collection_name="documents"
        )

        # Upsert pre-computed embeddings directly into the underlying collection
        vectorstore._collection.upsert(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )

        print(f"✅ Vector store created successfully with {len(embeddings)} chunks")
        return vectorstore

    def add_documents(self, vectorstore: Chroma, chunks: List[Document]) -> None:
        """Incrementally add new chunks to an existing vector store."""
        if not chunks:
            return

        texts = [c.page_content for c in chunks]
        metadatas = [c.metadata for c in chunks]

        # Get max existing ID to avoid collisions
        try:
            existing = vectorstore._collection.get(limit=1)
            start_id = len(existing.get("ids", []))
        except Exception:
            start_id = 0

        ids = [str(start_id + i) for i in range(len(chunks))]

        embeddings = self.embedder.embed_documents(texts)

        vectorstore._collection.upsert(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        print(f"✅ Added {len(embeddings)} chunks to existing vector store")

    def search_similar(self, vectorstore: Chroma, query: str, k: int = 8) -> List[Document]:
        try:
            results = vectorstore.similarity_search(query, k=k)
            return results
        except Exception as e:
            print(f"❌ Error searching vector store: {e}")
            return []
