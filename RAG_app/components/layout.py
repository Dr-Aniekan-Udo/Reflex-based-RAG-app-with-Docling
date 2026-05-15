"""
Layout component - Sidebar with per-document cards + main wrapper.
Sidebar: 350px, scrollable document list, persistent stats footer.
"""
import reflex as rx
from ..state.base_state import BaseState
from ..state.upload_state import UploadState


def document_card(doc) -> rx.Component:
    """Render a single document card with status-aware actions."""
    is_uploaded = doc["status"] == "uploaded"
    is_processing = doc["status"] == "processing"
    is_completed = doc["status"] == "completed"
    is_error = doc["status"] == "error"
    is_stopped = doc["status"] == "stopped"

    status_color = rx.cond(
        is_processing, "orange",
        rx.cond(is_completed, "green",
            rx.cond(is_error, "red",
                rx.cond(is_stopped, "amber", "gray")))
    )

    primary_btn = rx.cond(
        is_uploaded,
        rx.button(
            rx.hstack(rx.icon("play", size=12), rx.text("Process", size="1"), spacing="1"),
                    on_click=lambda: UploadState.process_document(doc["doc_id"]),
            color_scheme="orange",
            size="1",
            flex="1",
        ),
        rx.cond(
            is_processing,
            rx.button(
                rx.hstack(rx.icon("square", size=12), rx.text("Stop", size="1"), spacing="1"),
                on_click=lambda: UploadState.stop_processing(doc["doc_id"]),
                color_scheme="amber",
                size="1",
                flex="1",
            ),
            rx.cond(
                is_error | is_stopped,
                rx.button(
                    rx.hstack(rx.icon("rotate-ccw", size=12), rx.text("Retry", size="1"), spacing="1"),
                    on_click=lambda: UploadState.retry_document(doc["doc_id"]),
                    color_scheme="blue",
                    size="1",
                    flex="1",
                ),
                rx.button(
                    rx.hstack(rx.icon("refresh-cw", size=12), rx.text("Reprocess", size="1"), spacing="1"),
            on_click=lambda: UploadState.process_document(doc["doc_id"]),
                    color_scheme="orange",
                    size="1",
                    flex="1",
                ),
            ),
        ),
    )

    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("file-text", size=14, color=status_color),
                rx.text(doc["filename"], size="1", weight="medium", truncate=True, flex="1"),
                rx.text(f"{doc['size_mb']} MB", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                spacing="2",
                align="center",
                width="100%",
            ),
            rx.cond(
                is_processing,
                rx.vstack(
                    rx.progress(
                        value=doc["progress"],
                        width="100%",
                        color_scheme="orange",
                        height="4px",
                    ),
                    rx.text(doc["message"], size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                    spacing="1",
                    width="100%",
                ),
            ),
            rx.cond(
                is_error,
                rx.text(doc["error_message"], size="1", color="red", truncate=True),
            ),
            rx.cond(
                is_completed,
                rx.text(f"{doc['pages']} pages • {doc['chunks']} chunks", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
            ),
            rx.hstack(
                primary_btn,
                rx.icon_button(
                    rx.icon("trash-2", size=12),
                    on_click=lambda: UploadState.clear_document(doc["doc_id"]),
                    variant="soft",
                    color_scheme="red",
                    size="1",
                ),
                spacing="2",
                width="100%",
            ),
            spacing="2",
            width="100%",
        ),
        padding="0.5em",
        variant="ghost",
        width="100%",
    )


def sidebar() -> rx.Component:
    """Modern sidebar with per-document cards and persistent footer."""

    # ─── Fixed top section ───
    top_section = rx.vstack(
        rx.hstack(
            rx.icon("bot", size=28, color="orange"),
            rx.heading("RAG AI", size="5", weight="bold"),
            spacing="3",
            align="center",
            width="100%",
            padding_bottom="1em",
        ),
        rx.divider(),
        rx.heading("📤 Upload", size="3", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11)), width="100%"),
        rx.upload(
            rx.vstack(
                rx.icon("cloud-upload", size=32, color="orange"),
                rx.text("Drop or click to add files", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                spacing="2",
            ),
            id="upload_files",
            border=f"2px dashed {rx.color('orange', 6)}",
            padding="1.5em",
            multiple=True,
            accept={
                "application/pdf": [".pdf"],
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
                "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
                "text/html": [".html", ".htm"],
            },
            max_files=10,
            width="100%",
            _hover={
                "border_color": rx.color("orange", 8),
                "background": rx.color("orange", 2),
            },
            on_drop=UploadState.handle_upload(
                rx.upload_files(upload_id="upload_files")
            ),
        ),
        spacing="3",
        width="100%",
    )

    # ─── Scrollable documents list ───
    doc_list = rx.cond(
        UploadState.has_documents,
        rx.vstack(
            rx.hstack(
                rx.heading("Documents", size="2", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                rx.badge(UploadState.documents.length(), size="1", color_scheme="gray"),
                spacing="2",
                align="center",
                width="100%",
            ),
            rx.foreach(
                UploadState.documents,
                document_card,
            ),
            spacing="2",
            width="100%",
            overflow_y="auto",
            flex="1",
            min_height="0",
        ),
        rx.vstack(
                rx.icon("cloud-upload", size=32, color=rx.color("slate", 8)),
            rx.text("No documents yet", size="2", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
            rx.text("Drop files above to get started", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
            align="center",
            justify="center",
            width="100%",
            padding_y="2em",
        ),
    )

    # ─── Fixed bottom section ───
    bottom_section = rx.vstack(
        rx.divider(),
        rx.cond(
            UploadState.has_documents,
            rx.hstack(
                rx.button(
                    rx.hstack(rx.icon("play", size=14), rx.text("Process All", size="1"), spacing="2"),
                    on_click=UploadState.process_all_documents,
                    disabled=UploadState.is_processing_any,
                    color_scheme="orange",
                    size="2",
                    flex="1",
                ),
                rx.button(
                    rx.hstack(rx.icon("trash-2", size=14), rx.text("Clear All", size="1"), spacing="2"),
                    on_click=UploadState.clear_all_documents,
                    variant="soft",
                    color_scheme="red",
                    size="2",
                ),
                spacing="2",
                width="100%",
            ),
        ),
        rx.heading("📊 Stats", size="3", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11)), width="100%", margin_top="1em"),
        rx.grid(
            rx.card(
                rx.vstack(
                    rx.icon("file-text", size=18, color="orange"),
                    rx.text(UploadState.document_stats["total_files"], size="4", weight="bold"),
                    rx.text("Files", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                    align="center",
                    spacing="1",
                ),
                padding="0.75em",
                _hover={"transform": "translateY(-2px)"},
            ),
            rx.card(
                rx.vstack(
                    rx.icon("hard-drive", size=18, color="sky"),
                    rx.text(f"{UploadState.document_stats['total_size_mb']}MB", size="4", weight="bold"),
                    rx.text("Size", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                    align="center",
                    spacing="1",
                ),
                padding="0.75em",
                _hover={"transform": "translateY(-2px)"},
            ),
            rx.card(
                rx.vstack(
                    rx.icon("book-open", size=18, color="grass"),
                    rx.text(UploadState.document_stats["total_pages"], size="4", weight="bold"),
                    rx.text("Pages", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                    align="center",
                    spacing="1",
                ),
                padding="0.75em",
                _hover={"transform": "translateY(-2px)"},
            ),
            rx.card(
                rx.vstack(
                    rx.icon("link", size=18, color="violet"),
                    rx.text(UploadState.document_stats["vector_count"], size="4", weight="bold"),
                    rx.text("Vectors", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                    align="center",
                    spacing="1",
                ),
                padding="0.75em",
                _hover={"transform": "translateY(-2px)"},
            ),
            columns="2",
            spacing="2",
            width="100%",
        ),
        rx.text(
            f"Session: {BaseState.session_id[:8]}...",
            size="1",
            color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11)),
            width="100%",
            text_align="center",
        ),
        rx.hstack(
            rx.icon_button(
                rx.color_mode_cond(
                    light=rx.icon("moon", size=16),
                    dark=rx.icon("sun", size=16),
                ),
                on_click=rx.toggle_color_mode,
                variant="ghost",
                color_scheme="orange",
                size="2",
            ),
            rx.spacer(),
            rx.text("v2.0", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
            width="100%",
        ),
        spacing="3",
        width="100%",
        padding_top="1em",
    )

    return rx.box(
        rx.vstack(
            top_section,
            rx.box(
                doc_list,
                flex="1",
                min_height="0",
                overflow_y="auto",
                width="100%",
            ),
            bottom_section,
            spacing="3",
            height="100dvh",
            padding="1.5em",
            width="100%",
        ),
        width="350px",
        height="100dvh",
        position="sticky",
        top="0",
        left="0",
        background=rx.color_mode_cond(
            light=rx.color("slate", 2),
            dark="#0c0a09",
        ),
        border_right=f"1px solid {rx.color_mode_cond(light=rx.color('slate', 4), dark='rgba(255,255,255,0.08)')}",
        overflow="hidden",
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
            background=rx.color_mode_cond(
                light=rx.color("slate", 1),
                dark="#0c0a09",
            ),
        ),
        spacing="0",
        align_items="start",
        height="100dvh",
        width="100%",
    )
