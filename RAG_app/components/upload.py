"""
Upload component - Two-step file upload and processing.
Step 1: Drop files (auto-reads into memory)
Step 2: Click Process & Vectorize
"""
import reflex as rx
from ..state.upload_state import UploadState


def upload_view() -> rx.Component:
    """Document upload and processing interface."""
    return rx.card(
        rx.vstack(
            rx.heading("📤 Document Ingestion", size="4", margin_bottom="0.5em"),

            # Upload zone
            rx.upload(
                rx.vstack(
                    rx.button(
                        "Select Documents",
                        color_scheme="blue",
                        size="2",
                    ),
                    rx.text(
                        "Drag and drop documents here (PDF, DOCX, PPTX, HTML)",
                        size="2",
                        color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11)),
                    ),
                    spacing="2",
                ),
                id="upload_files",
                border="2px dashed #cbd5e0",
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
                background="#f7fafc",
                on_drop=UploadState.handle_upload(
                    rx.upload_files(upload_id="upload_files")
                ),
            ),

            # Files selected display
            rx.cond(
                UploadState.uploaded_files.length() > 0,
                rx.box(
                    rx.heading("📋 Files Ready", size="3", margin_bottom="0.5em"),
                    rx.vstack(
                        rx.foreach(
                            UploadState.uploaded_files,
                            lambda file_info: rx.hstack(
                                rx.icon("file", size=16, color="blue"),
                                rx.text(file_info["name"], size="2", flex="1"),
                                rx.text(
                                    f"({file_info['size_mb']} MB)",
                                    size="1",
                                    color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11)),
                                ),
                                rx.badge("Ready", color_scheme="blue", size="1"),
                                spacing="2",
                                width="100%",
                                align="center",
                            ),
                        ),
                        align="start",
                        spacing="1",
                        width="100%",
                    ),
                    margin_top="1em",
                    padding="1em",
                    background="#e3f2fd",
                    border="1px solid #2196f3",
                    border_radius="6px",
                ),
            ),

            # Control buttons
            rx.hstack(
                rx.button(
                    "🚀 Process & Vectorize",
                    on_click=UploadState.start_processing,
                    loading=UploadState.is_processing,
                    disabled=(
                        UploadState.is_processing
                        | (UploadState.uploaded_files.length() == 0)
                    ),
                    variant="surface",
                    color_scheme="green",
                ),
                rx.button(
                    "🗑️ Clear All",
                    on_click=UploadState.clear_documents,
                    disabled=UploadState.is_processing,
                    variant="soft",
                    color_scheme="red",
                ),
                spacing="3",
                margin_top="1em",
                width="100%",
                justify="end",
            ),

            rx.divider(margin_y="1em"),

            # Status message
            rx.text(
                UploadState.current_task_message,
                size="2",
                weight="bold",
                color="#2d3748",
            ),

            # Progress section
            rx.cond(
                UploadState.process_progress > 0,
                rx.box(
                    rx.text("Processing Progress", size="1", margin_top="0.5em"),
                    rx.progress(
                        value=UploadState.process_progress,
                        width="100%",
                        color_scheme="green",
                        height="8px",
                    ),
                    background="#ebf8ff",
                    padding="0.75em",
                    border_radius="6px",
                    width="100%",
                    margin_top="0.5em",
                ),
            ),

            # Processed files
            rx.cond(
                UploadState.processed_files.length() > 0,
                rx.box(
                    rx.heading("✅ Processed Files", size="3", margin_bottom="0.25em"),
                    rx.text("These documents are ready for chat queries", size="1", color=rx.color_mode_cond(light=rx.color("slate", 11), dark=rx.color("slate", 11)), margin_bottom="0.25em"),
                    rx.vstack(
                        rx.foreach(
                            UploadState.processed_files,
                            lambda filename: rx.hstack(
                                rx.icon("check", size=16, color="green"),
                                rx.text(filename, size="2"),
                                rx.badge("Vectorized", color_scheme="green", size="1"),
                                spacing="2",
                            ),
                        ),
                        align="start",
                        spacing="1",
                    ),
                    margin_top="0.75em",
                    padding="0.75em",
                    background="#e8f5e9",
                    border="1px solid #4caf50",
                    border_radius="6px",
                ),
            ),

            width="100%",
            align="start",
        ),
        width="100%",
    )
