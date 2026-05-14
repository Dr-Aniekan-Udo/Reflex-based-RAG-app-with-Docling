"""
ProcessPoolExecutor singleton for offloading CPU-bound document processing.
"""
import os
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

_executor: ProcessPoolExecutor | None = None


def get_executor() -> ProcessPoolExecutor:
    """Get or create the ProcessPoolExecutor."""
    global _executor
    if _executor is None:
        mp_context = multiprocessing.get_context("spawn")
        max_workers = int(os.getenv("RAG_WORKER_PROCESSES", "2"))
        _executor = ProcessPoolExecutor(
            max_workers=max_workers,
            mp_context=mp_context,
        )
    return _executor


def shutdown_executor():
    """Shutdown the executor gracefully."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None
