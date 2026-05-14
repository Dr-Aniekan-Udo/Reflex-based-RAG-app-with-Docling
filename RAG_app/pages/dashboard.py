"""
Dashboard page - Main RAG interface.
"""
import reflex as rx
from ..components.layout import layout
from ..components.upload import upload_view
from ..components.chat import chat_interface
from ..components.structure import structure_view
from ..state.base_state import BaseState
from ..state.structure_state import StructureState


def index() -> rx.Component:
    """Main dashboard view"""
    return layout(
        rx.vstack(
            rx.heading("📄 Enterprise Document Intelligence", size="7", margin_bottom="0.2em"),
            rx.text(
                "Secure, modular RAG architecture powered by Reflex, Docling, and LangGraph.",
                color="gray",
                size="3",
                margin_bottom="2em",
            ),

            # Main tabs
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("💬 Chat Interface", value="chat"),
                    rx.tabs.trigger("📊 Document Analysis", value="structure"),
                ),

                # Chat tab
                rx.tabs.content(
                    rx.grid(
                        rx.box(upload_view()),
                        rx.box(chat_interface()),
                        columns="2",
                        spacing="6",
                        width="100%",
                    ),
                    value="chat",
                ),

                # Structure tab
                rx.tabs.content(
                    rx.box(
                        structure_view(),
                        on_mount=StructureState.load_available_documents,
                    ),
                    value="structure",
                ),

                default_value="chat",
                width="100%",
            ),

            width="100%",
            max_width="1400px",
            margin_x="auto",
        ),
    )
