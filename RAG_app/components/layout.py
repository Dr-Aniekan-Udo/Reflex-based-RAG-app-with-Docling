"""
Layout component - Sidebar + main wrapper.
"""
import reflex as rx
from ..state.base_state import BaseState
from ..state.upload_state import UploadState


def stats_card(label: str, value: str) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="gray"),
        rx.text(value, size="3", weight="bold"),
        align="start",
        spacing="0",
    )


def sidebar() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("📄 RAG App", size="5", color="white"),
            rx.divider(border_color="gray.600"),
            rx.link("Dashboard", href="/", color="white"),
            rx.spacer(),
            rx.heading("Session Stats", size="3", color="white"),
            stats_card("Files", UploadState.document_stats["total_files"]),
            stats_card("Size (MB)", UploadState.document_stats["total_size_mb"]),
            stats_card("Pages", UploadState.document_stats["total_pages"]),
            stats_card("Vectors", UploadState.document_stats["vector_count"]),
            rx.spacer(),
            rx.heading("Session ID", size="3", color="white"),
            rx.text(BaseState.session_id[:8] + "...", size="1", color="gray"),
            spacing="4",
            height="100%",
            padding="1.5em",
        ),
        width="240px",
        height="100dvh",
        position="sticky",
        top="0",
        background="#1a202c",
        color="white",
    )


def layout(content: rx.Component) -> rx.Component:
    return rx.hstack(
        sidebar(),
        rx.box(
            content,
            flex="1",
            padding="1.5em",
            overflow_y="auto",
            height="100dvh",
        ),
        spacing="0",
        align_items="start",
        height="100dvh",
        width="100%",
    )
