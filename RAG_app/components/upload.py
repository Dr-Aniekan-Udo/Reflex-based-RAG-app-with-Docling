"""
Upload component - File upload interface with progress tracking.
"""
import reflex as rx
from ..state.process_state import ProcessState


def upload_view() -> rx.Component:
    """Document upload and processing interface"""
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
            ),
            
            # Control buttons
            rx.hstack(
                rx.button(
                    "📤 Upload Files",
                    on_click=ProcessState.handle_upload(
                        rx.upload_files(upload_id="upload_files")
                    ),
                    loading=ProcessState.is_uploading,
                    variant="solid",
                    color_scheme="blue",
                ),
                rx.button(
                    "🚀 Process & Vectorize",
                    on_click=ProcessState.start_vectorization,
                    disabled=ProcessState.is_uploading | ProcessState.is_processing,
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
            
            # Uploaded files list
            rx.cond(
                ProcessState.uploaded_files,
                rx.box(
                    rx.heading("📁 Uploaded Files", size="3", margin_bottom="0.5em"),
                    rx.vstack(
                        rx.foreach(
                            ProcessState.uploaded_files,
                            lambda filename: rx.hstack(
                                rx.icon("file", size=16, color="blue"),
                                rx.text(filename, size="2"),
                                spacing="2",
                            ),
                        ),
                        align="start",
                        spacing="1",
                    ),
                    margin_top="1em",
                    padding="1em",
                    background="#f7fafc",
                    border_radius="6px",
                ),
            ),
            
            width="100%",
            align="start",
        ),
        width="100%",
    )
