"""
Vector store management for document storage and retrieval.
Synchronous; the caller (Reflex background task) is responsible for threading.
"""
import os
import time
from typing import List, Tuple
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# The installed langchain-google-genai (>=4.x) uses the new Google GenAI SDK.
# The correct embedding model name is "gemini-embedding-2-preview".
# Older names like "models/text-embedding-004" are not supported by this SDK.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")

# Embedding rate-limit configuration (tune for your API tier)
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "25"))
EMBEDDING_RPM_LIMIT = int(os.getenv("EMBEDDING_RPM_LIMIT", "5"))
EMBEDDING_MAX_RETRIES = int(os.getenv("EMBEDDING_MAX_RETRIES", "5"))


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

    def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts with batching, rate-limit pacing, and retry.
        Never skips chunks — raises on persistent failure so the caller
        can surface the error in the UI.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        delay_between_batches = 60.0 / EMBEDDING_RPM_LIMIT  # e.g. 12s for 5 RPM

        for batch_start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[batch_start:batch_start + EMBEDDING_BATCH_SIZE]
            batch_num = batch_start // EMBEDDING_BATCH_SIZE + 1
            total_batches = (len(texts) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
            print(f"  📦 Embedding batch {batch_num}/{total_batches} ({len(batch)} texts)...")

            last_error = None
            for attempt in range(1, EMBEDDING_MAX_RETRIES + 1):
                try:
                    embeddings = self.embeddings.embed_documents(batch)
                    if len(embeddings) != len(batch):
                        raise ValueError(
                            f"Embedding count mismatch: got {len(embeddings)}, expected {len(batch)}"
                        )
                    all_embeddings.extend(embeddings)
                    print(f"  ✅ Batch {batch_num} complete ({len(embeddings)} embeddings)")
                    break
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    is_rate_limit = (
                        "429" in error_msg
                        or "RESOURCE_EXHAUSTED" in error_msg
                        or "Too Many Requests" in error_msg
                        or "rate limit" in error_msg.lower()
                    )

                    if is_rate_limit and attempt < EMBEDDING_MAX_RETRIES:
                        wait = min(2 ** attempt, 30)  # Exponential backoff capped at 30s
                        print(f"  ⏳ Rate limit hit, retrying in {wait}s (attempt {attempt}/{EMBEDDING_MAX_RETRIES})...")
                        time.sleep(wait)
                    else:
                        # Final attempt failed — raise so the task fails visibly
                        raise RuntimeError(
                            f"Embedding failed after {attempt} attempts: {error_msg}"
                        ) from last_error

            # Rate-limit pacing between batches (skip after the last batch)
            if batch_start + EMBEDDING_BATCH_SIZE < len(texts):
                print(f"  ⏱️  Waiting {delay_between_batches:.1f}s for rate limit...")
                time.sleep(delay_between_batches)

        return all_embeddings

    def create_vectorstore(self, chunks: List[Document]) -> Chroma:
        print(f"🔢 Creating vector store with {len(chunks)} chunks...")

        texts = [c.page_content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = [str(i) for i in range(len(chunks))]

        embeddings = self._embed_batch_with_retry(texts)

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

        embeddings = self._embed_batch_with_retry(texts)

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
