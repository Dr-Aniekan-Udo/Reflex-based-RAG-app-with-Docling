"""
Upload component - File upload interface with progress tracking.
Shows file selection buffer, upload status, and processed files.
"""
import reflex as rx
from ..state.process_state import ProcessState


def upload_view() -> rx.Component:
    """Document upload and processing interface with file selection buffer"""
    return rx.card(
        rx.vstack(
            rx.heading("📤 Document Ingestion", size="4", margin_bottom="1em"),
            
            # Upload zone
            rx.upload(
                rx.vstack(
                    rx.button(
                        "Select Documents",
                        color_scheme="blue",
                        size="3",
                    ),
                    rx.text(
                        "Drag and drop PDF files here",
                        size="2",
                        color="gray",
                    ),
                    spacing="2",
                ),
                id="upload_files",
                border="2px dashed #cbd5e0",
                padding="2em",
                multiple=True,
                accept={"application/pdf": [".pdf"]},
                max_files=10,
                width="100%",
                background="#f7fafc",
                on_drop=ProcessState.handle_file_selection(
                    rx.upload_files(upload_id="upload_files")
                ),
            ),
            
            # File Selection Buffer (shows immediately when files are selected)
            rx.cond(
                ProcessState.selected_files,
                rx.box(
                    rx.heading("📋 Selected Files", size="3", margin_bottom="0.5em"),
                    rx.vstack(
                        rx.foreach(
                            ProcessState.selected_files,
                            lambda filename: rx.hstack(
                                rx.icon("file", size=16, color="blue"),
                                rx.text(filename, size="2", flex="1"),
                                rx.icon_button(
                                    rx.icon("x", size=16),
                                    on_click=ProcessState.remove_selected_file(filename),
                                    size="1",
                                    variant="ghost",
                                    color_scheme="red",
                                ),
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
                    background="#fff3cd",
                    border="1px solid #ffc107",
                    border_radius="6px",
                ),
            ),
            
            # Control buttons
            rx.hstack(
                rx.button(
                    "📤 Upload Files",
                    on_click=ProcessState.handle_upload(
                        rx.upload_files(upload_id="upload_files")
                    ),
                    loading=ProcessState.is_uploading,
                    disabled=~ProcessState.selected_files.length(),
                    variant="solid",
                    color_scheme="blue",
                ),
                rx.button(
                    "🚀 Process & Vectorize",
                    on_click=ProcessState.start_vectorization,
                    disabled=ProcessState.is_uploading | ProcessState.is_processing | ~ProcessState.uploaded_files.length(),
                    variant="surface",
                    color_scheme="green",
                ),
                rx.button(
                    "🗑️ Clear All",
                    on_click=ProcessState.clear_documents,
                    disabled=ProcessState.is_uploading | ProcessState.is_processing,
                    variant="soft",
                    color_scheme="red",
                ),
                spacing="3",
                margin_top="1em",
                width="100%",
                justify="end",
            ),
            
            rx.divider(margin_y="1.5em"),
            
            # Progress section
            rx.cond(
                (ProcessState.upload_progress > 0) | (ProcessState.process_progress > 0),
                rx.box(
                    rx.text(
                        ProcessState.current_task_message,
                        size="2",
                        weight="bold",
                        color="#2d3748",
                    ),
                    
                    rx.text("Upload Progress", size="1", margin_top="0.5em"),
                    rx.progress(
                        value=ProcessState.upload_progress,
                        width="100%",
                        color_scheme="blue",
                        height="8px",
                    ),
                    
                    rx.text("Processing Progress", size="1", margin_top="0.5em"),
                    rx.progress(
                        value=ProcessState.process_progress,
                        width="100%",
                        color_scheme="green",
                        height="8px",
                    ),
                    
                    background="#ebf8ff",
                    padding="1em",
                    border_radius="6px",
                    width="100%",
                ),
            ),
            
            # Uploaded files (in memory, ready to process)
            rx.cond(
                ProcessState.uploaded_files & ~ProcessState.processed_files.length(),
                rx.box(
                    rx.heading("💾 Uploaded to Memory", size="3", margin_bottom="0.5em"),
                    rx.text("Files are ready for processing", size="1", color="gray", margin_bottom="0.5em"),
                    rx.vstack(
                        rx.foreach(
                            ProcessState.uploaded_files,
                            lambda filename: rx.hstack(
                                rx.icon("file", size=16, color="orange"),
                                rx.text(filename, size="2"),
                                rx.badge("In Memory", color_scheme="orange", size="1"),
                                spacing="2",
                            ),
                        ),
                        align="start",
                        spacing="1",
                    ),
                    margin_top="1em",
                    padding="1em",
                    background="#fff8e1",
                    border="1px solid #ffb300",
                    border_radius="6px",
                ),
            ),
            
            # Processed files (vectorized and indexed)
            rx.cond(
                ProcessState.processed_files,
                rx.box(
                    rx.heading("✅ Processed Files", size="3", margin_bottom="0.5em"),
                    rx.text("These documents are ready for chat queries", size="1", color="gray", margin_bottom="0.5em"),
                    rx.vstack(
                        rx.foreach(
                            ProcessState.processed_files,
                            lambda filename: rx.hstack(
                                rx.icon("check-circle", size=16, color="green"),
                                rx.text(filename, size="2"),
                                rx.badge("Vectorized", color_scheme="green", size="1"),
                                spacing="2",
                            ),
                        ),
                        align="start",
                        spacing="1",
                    ),
                    margin_top="1em",
                    padding="1em",
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
