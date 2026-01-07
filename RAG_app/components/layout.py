"""
Layout components - Sidebar and page wrappers.
"""
import reflex as rx
from ..state.process_state import ProcessState


def stats_card(label: str, value: str, icon: str) -> rx.Component:
    """Reusable stats card for sidebar"""
    return rx.box(
        rx.hstack(
            rx.icon(icon, size=20, color="white"),
            rx.vstack(
                rx.text(label, size="1", color="#a0aec0"),
                rx.text(value, size="3", weight="bold", color="white"),
                spacing="0",
            ),
            spacing="3",
            align="center",
        ),
        padding="1em",
        background="rgba(255, 255, 255, 0.1)",
        border_radius="8px",
        width="100%",
        margin_bottom="0.5em",
    )


def sidebar() -> rx.Component:
    """Application sidebar with navigation and stats"""
    return rx.box(
        rx.vstack(
            rx.heading("📄 Enterprise RAG", size="5", color="white", margin_bottom="1.5em"),
            
            # Navigation
            rx.link(
                rx.hstack(
                    rx.icon("layout-dashboard"),
                    rx.text("Dashboard"),
                    spacing="2",
                ),
                href="/",
                color="white",
                text_decoration="none",
                width="100%",
                padding="0.5em",
                border_radius="6px",
                _hover={"background": "rgba(255,255,255,0.05)"},
            ),
            
            rx.divider(margin_y="2em", border_color="#4a5568"),
            
            # System statistics
            rx.text("SYSTEM STATUS", size="1", weight="bold", color="#718096"),
            
            stats_card(
                "Files Ingested",
                ProcessState.document_stats["total_files"].to(str),
                "file-text"
            ),
            stats_card(
                "Total Size",
                f"{ProcessState.document_stats['total_size_mb']} MB",
                "hard-drive"
            ),
            stats_card(
                "Total Pages",
                ProcessState.document_stats["total_pages"].to(str),
                "book-open"
            ),
            stats_card(
                "Active Vectors",
                ProcessState.document_stats["vector_count"].to(str),
                "database"
            ),
            
            align="start",
            padding="2em",
        ),
        width="280px",
        height="100vh",
        background="#1a202c",
        position="sticky",
        top="0",
    )


def layout(content: rx.Component) -> rx.Component:
    """Main layout wrapper with sidebar"""
    return rx.hstack(
        sidebar(),
        rx.box(
            content,
            width="100%",
            height="100vh",
            padding="2em",
            overflow_y="auto",
            background="#f7fafc",
        ),
        spacing="0",
    )
