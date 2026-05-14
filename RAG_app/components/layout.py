"""
Layout component - Sidebar with integrated upload + main wrapper.
"""
import reflex as rx
from ..state.base_state import BaseState
from ..state.upload_state import UploadState


def sidebar() -> rx.Component:
    """Modern sidebar with upload, stats, and theme toggle."""
    return rx.box(
        rx.vstack(
            # ─── Brand Header ───
            rx.hstack(
                rx.icon("bot", size=28, color="orange"),
                rx.heading("RAG AI", size="5", weight="bold"),
                spacing="3",
                align="center",
                width="100%",
                padding_bottom="1em",
            ),
            rx.divider(),

            # ─── Document Ingestion ───
            rx.heading("📤 Upload", size="3", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11)), width="100%"),
            rx.upload(
                rx.vstack(
                    rx.icon("upload-cloud", size=32, color="orange"),
                    rx.text("Drop PDF, DOCX, PPTX, HTML", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
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

            # File list
            rx.cond(
                UploadState.uploaded_files.length() > 0,
                rx.vstack(
                    rx.foreach(
                        UploadState.uploaded_files,
                        lambda file_info: rx.card(
                            rx.hstack(
                                rx.icon("file-text", size=14, color="orange"),
                                rx.text(file_info["name"], size="1", truncate=True, flex="1"),
                                rx.text(f"{file_info['size_mb']} MB", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                                spacing="2",
                                align="center",
                            ),
                            padding="0.5em",
                            variant="ghost",
                            width="100%",
                        ),
                    ),
                    spacing="1",
                    width="100%",
                ),
            ),

            # Buttons
            rx.hstack(
                rx.button(
                    "🚀 Process",
                    on_click=UploadState.start_processing,
                    loading=UploadState.is_processing,
                    disabled=(
                        UploadState.is_processing
                        | (UploadState.uploaded_files.length() == 0)
                    ),
                    color_scheme="orange",
                    size="2",
                    width="100%",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("trash-2", size=14),
                        rx.text("Clear", size="1"),
                        spacing="2",
                    ),
                    on_click=UploadState.clear_documents,
                    disabled=UploadState.is_processing,
                    variant="soft",
                    color_scheme="red",
                    size="2",
                ),
                spacing="2",
                width="100%",
            ),

            # Progress
            rx.cond(
                UploadState.process_progress > 0,
                rx.vstack(
                    rx.progress(
                        value=UploadState.process_progress,
                        width="100%",
                        color_scheme="orange",
                        height="6px",
                    ),
                    rx.text(UploadState.current_task_message, size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                    spacing="1",
                    width="100%",
                ),
            ),

            rx.divider(),

            # ─── Session Stats ───
            rx.heading("📊 Stats", size="3", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11)), width="100%"),
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

            rx.spacer(),

            # ─── Footer ───
            rx.divider(),
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
                rx.text("v1.0", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11))),
                width="100%",
            ),

            spacing="3",
            height="100%",
            padding="1.5em",
            width="100%",
        ),
        width="300px",
        height="100dvh",
        position="sticky",
        top="0",
        left="0",
        background=rx.color_mode_cond(
            light=rx.color("slate", 2),
            dark="#0c0a09",
        ),
        border_right=f"1px solid {rx.color_mode_cond(light=rx.color('slate', 4), dark='rgba(255,255,255,0.08)')}",
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
