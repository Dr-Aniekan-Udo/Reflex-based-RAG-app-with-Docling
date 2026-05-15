"""
Dashboard page - Main RAG interface.
"""
import reflex as rx
from ..components.layout import layout
from ..components.chat import chat_interface
from ..components.structure import structure_view
from ..state.base_state import BaseState
from ..state.structure_state import StructureState


def index() -> rx.Component:
    """Main dashboard view"""
    return rx.fragment(
        rx.title("RAG AI Assistant"),
        rx.meta(name="description", content="Intelligent document analysis with RAG"),
        layout(
        rx.vstack(
            # ─── Tabs ───
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger(
                        rx.hstack(rx.icon("message-square"), rx.text("Chat"), spacing="2"),
                        value="chat",
                    ),
                    rx.tabs.trigger(
                        rx.hstack(rx.icon("bar-chart-3"), rx.text("Analysis"), spacing="2"),
                        value="structure",
                    ),
                    justify="center",
                    background=rx.color_mode_cond(
                        light=rx.color("slate", 3),
                        dark=rx.color("slate", 3),
                    ),
                    border_radius="full",
                    padding="0.25em",
                ),

                # Chat tab
                rx.tabs.content(
                    rx.box(
                        chat_interface(),
                        height="calc(100dvh - 120px)",
                        min_height="400px",
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
                        height="calc(100dvh - 120px)",
                        min_height="400px",
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
            max_width="1200px",
            margin_x="auto",
            height="100%",
            spacing="0",
            min_height="0",
        ),
        ),
    )
