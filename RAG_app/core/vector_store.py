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

# The installed langchain-google-genai (>=4.x) uses the new Google GenAI SDK.
# The correct embedding model name is "gemini-embedding-2-preview".
# Older names like "models/text-embedding-004" are not supported by this SDK.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")


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
        # Filter out empty/whitespace-only chunks to prevent embedding length mismatch
        chunks = [c for c in chunks if c.page_content and c.page_content.strip()]
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
