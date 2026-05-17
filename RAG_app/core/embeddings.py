"""
Google Gemini embedding client that bypasses the langchain-google-genai
batch embedding bug (Issue #1704).

Uses the official google-genai SDK directly for correct batch embedding.
https://github.com/langchain-ai/langchain-google/issues/1704
"""
import os
import time
from typing import List, Optional

from google import genai
from google.genai import types
from google.genai.errors import APIError

from .logging_config import logger

# Configurable via environment variables
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")
DEFAULT_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))  # Google limit
DEFAULT_RPM_LIMIT = int(os.getenv("EMBEDDING_RPM_LIMIT", "5"))       # Free tier
DEFAULT_MAX_RETRIES = int(os.getenv("EMBEDDING_MAX_RETRIES", "5"))


class GeminiEmbedder:
    """
    Production-grade Gemini embedding client.

    - Batches up to 100 texts per API call (Google's limit)
    - Pre-wraps each text in a Content object to avoid the langchain bug
    - Retries on 429 rate-limit errors with exponential backoff
    - Never silently skips chunks — raises on persistent failure
    """

    def __init__(
        self,
        model: Optional[str] = None,
        dimensionality: Optional[int] = None,
        batch_size: Optional[int] = None,
        rpm_limit: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self.client = genai.Client()  # Reads GOOGLE_API_KEY from env
        self.model = model or DEFAULT_MODEL
        self.dimensionality = dimensionality
        self.batch_size = batch_size or DEFAULT_BATCH_SIZE
        self.rpm_limit = rpm_limit or DEFAULT_RPM_LIMIT
        self.max_retries = max_retries or DEFAULT_MAX_RETRIES
        self._delay_between_batches = 60.0 / self.rpm_limit  # e.g. 12s for 5 RPM

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts. Returns one embedding per text.

        Batches texts into groups of ``batch_size``, adds rate-limit
        delays between batches, and retries on 429 errors.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        total = len(texts)
        total_batches = (total + self.batch_size - 1) // self.batch_size

        for batch_idx in range(total_batches):
            start = batch_idx * self.batch_size
            batch = texts[start : start + self.batch_size]
            batch_num = batch_idx + 1

            logger.info(
                "embedding_batch_start",
                batch_num=batch_num,
                total_batches=total_batches,
                batch_size=len(batch),
                model=self.model,
            )

            embeddings = self._embed_batch(batch)
            all_embeddings.extend(embeddings)

            logger.info(
                "embedding_batch_complete",
                batch_num=batch_num,
                total_batches=total_batches,
                embeddings_returned=len(embeddings),
            )

            # Rate-limit pacing between batches (skip after last batch)
            if batch_num < total_batches:
                logger.info(
                    "embedding_rate_limit_wait",
                    seconds=self._delay_between_batches,
                )
                time.sleep(self._delay_between_batches)

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        embeddings = self.embed_documents([text])
        if not embeddings:
            raise RuntimeError("Empty embedding returned for query")
        return embeddings[0]

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Call the Gemini embedding API for one batch of texts.
        Pre-wraps each text in a Content object to avoid the
        langchain-google-genai #1704 bug.
        """
        # CRITICAL FIX: Wrap each text in its own Content object.
        # Passing a bare list[str] to the SDK causes it to merge
        # all strings into a single Content, returning 1 embedding
        # regardless of input count.
        contents = [types.Content(parts=[types.Part(text=t)]) for t in texts]

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                config = None
                if self.dimensionality is not None:
                    config = types.EmbedContentConfig(
                        output_dimensionality=self.dimensionality
                    )

                response = self.client.models.embed_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )

                embeddings = [emb.values for emb in response.embeddings]

                if len(embeddings) != len(texts):
                    raise ValueError(
                        f"Embedding count mismatch: got {len(embeddings)}, "
                        f"expected {len(texts)}"
                    )

                return embeddings

            except APIError as e:
                last_error = e
                error_msg = str(e)
                is_rate_limit = getattr(e, "code", None) == 429 or "429" in error_msg

                if is_rate_limit and attempt < self.max_retries:
                    wait = min(2 ** attempt, 30)  # Exponential backoff, cap at 30s
                    logger.warning(
                        "embedding_rate_limit_retry",
                        attempt=attempt,
                        max_retries=self.max_retries,
                        wait_seconds=wait,
                        error=error_msg,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "embedding_api_error",
                        attempt=attempt,
                        error=error_msg,
                    )
                    raise RuntimeError(
                        f"Embedding failed after {attempt} attempts: {error_msg}"
                    ) from last_error

        # Should never reach here, but guard anyway
        raise RuntimeError(
            f"Embedding failed after {self.max_retries} attempts"
        ) from last_error
