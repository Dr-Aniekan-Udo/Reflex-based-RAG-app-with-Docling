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

        texts = [c.page_content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = [str(i) for i in range(len(chunks))]

        # Attempt batch embedding first
        try:
            embeddings = self.embeddings.embed_documents(texts)
            if len(embeddings) != len(texts):
                print(
                    f"⚠️ Embedding count mismatch: {len(embeddings)} vs {len(texts)}. "
                    "Falling back to one-by-one embedding..."
                )
                raise ValueError("Embedding count mismatch")
        except Exception as batch_err:
            print(f"⚠️ Batch embedding failed ({batch_err}). Falling back to one-by-one embedding...")
            embeddings = []
            valid_texts = []
            valid_metadatas = []
            valid_ids = []
            for idx, text in enumerate(texts):
                try:
                    emb = self.embeddings.embed_query(text)
                    embeddings.append(emb)
                    valid_texts.append(text)
                    valid_metadatas.append(metadatas[idx])
                    valid_ids.append(ids[idx])
                except Exception as single_err:
                    print(f"⚠️ Skipping chunk {idx} due to embedding error: {single_err}")
                    continue

            texts = valid_texts
            metadatas = valid_metadatas
            ids = valid_ids
            print(f"✅ One-by-one embedding complete: {len(embeddings)} embeddings")

        # Create empty Chroma instance with embedding_function so similarity_search works later
        vectorstore = Chroma(
            embedding_function=self.embeddings,
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

        # Embed with fallback
        try:
            embeddings = self.embeddings.embed_documents(texts)
            if len(embeddings) != len(texts):
                raise ValueError("Embedding count mismatch")
        except Exception:
            embeddings = []
            valid_texts = []
            valid_metadatas = []
            valid_ids = []
            for idx, text in enumerate(texts):
                try:
                    emb = self.embeddings.embed_query(text)
                    embeddings.append(emb)
                    valid_texts.append(text)
                    valid_metadatas.append(metadatas[idx])
                    valid_ids.append(ids[idx])
                except Exception:
                    continue
            texts = valid_texts
            metadatas = valid_metadatas
            ids = valid_ids

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
