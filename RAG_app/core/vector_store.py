"""
Vector store management for document storage and retrieval.
Synchronous; the caller (Reflex background task) is responsible for threading.
"""
import os
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# Default to embedding-001 (widely supported on v1beta)
# text-embedding-004 may require newer API versions
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/embedding-001")


class VectorStoreManager:
    """Manages document chunking, embedding, and vector storage."""

    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=len,
        )

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        print(f"✂️ Chunking {len(documents)} documents...")
        chunks = self.text_splitter.split_documents(documents)
        print(f"✅ Created {len(chunks)} chunks")
        return chunks

    def create_vectorstore(self, chunks: List[Document]) -> Chroma:
        print(f"🔢 Creating vector store with {len(chunks)} chunks...")
        try:
            vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                collection_name="documents"
            )
            print("✅ Vector store created successfully")
            return vectorstore
        except Exception as e:
            print(f"❌ Error creating vector store: {e}")
            raise

    def search_similar(self, vectorstore: Chroma, query: str, k: int = 8) -> List[Document]:
        try:
            results = vectorstore.similarity_search(query, k=k)
            return results
        except Exception as e:
            print(f"❌ Error searching vector store: {e}")
            return []
