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
            rx.heading("📄 Enterprise Document Intelligence", size="6", margin_bottom="0.1em"),
            rx.text(
                "Secure, modular RAG architecture powered by Reflex, Docling, and LangGraph.",
                color="gray",
                size="2",
                margin_bottom="1em",
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
                        rx.box(upload_view(), height="100%"),
                        rx.box(chat_interface(), height="100%"),
                        columns="2",
                        spacing="4",
                        width="100%",
                        height="100%",
                        min_height="0",
                    ),
                    value="chat",
                    height="100%",
                    min_height="0",
                ),

                # Structure tab
                rx.tabs.content(
                    rx.box(
                        structure_view(),
                        on_mount=StructureState.load_available_documents,
                        height="100%",
                        min_height="0",
                        overflow_y="auto",
                    ),
                    value="structure",
                    height="100%",
                    min_height="0",
                ),

                default_value="chat",
                width="100%",
                flex="1",
                min_height="0",
            ),

            width="100%",
            max_width="1400px",
            margin_x="auto",
            height="100%",
            spacing="0",
            min_height="0",
        ),
    )
