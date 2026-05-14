"""
Chat component - Conversational interface with streaming responses.
"""
import reflex as rx
from ..state.chat_state import ChatState


def message_bubble(msg: dict) -> rx.Component:
    """Render a single chat message."""
    is_user = msg["role"] == "user"
    return rx.box(
        rx.markdown(msg["content"]),
        background=rx.cond(is_user, "#3182ce", "#edf2f7"),
        color=rx.cond(is_user, "white", "#2d3748"),
        padding_x="1em",
        padding_y="0.5em",
        border_radius=rx.cond(is_user, "15px 15px 0 15px", "0 15px 15px 15px"),
        align_self=rx.cond(is_user, "end", "start"),
        max_width="80%",
        box_shadow="sm",
        margin_bottom="0.5em",
    )


def chat_interface() -> rx.Component:
    """Main chat interface with history and input"""
    return rx.card(
        rx.vstack(
            # Header
            rx.hstack(
                rx.heading("💬 Knowledge Assistant", size="4"),
                rx.spacer(),
                rx.button(
                    "Clear History",
                    on_click=ChatState.clear_history,
                    variant="soft",
                    color_scheme="red",
                    size="1",
                ),
                width="100%",
                align="center",
                margin_bottom="0.5em",
            ),

            # Chat history area
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(
                        ChatState.chat_history,
                        message_bubble,
                    ),
                    width="100%",
                    padding="1em",
                ),
                height="60vh",
                width="100%",
                border="1px solid #e2e8f0",
                border_radius="8px",
                background="white",
                scrollbars="vertical",
            ),

            # Input area
            rx.hstack(
                rx.input(
                    placeholder="Ask a question about the uploaded documents...",
                    value=ChatState.current_question,
                    on_change=ChatState.set_question,
                    on_key_down=ChatState.handle_key_down,
                    width="100%",
                    border_color="#cbd5e0",
                ),
                rx.button(
                    rx.icon("send", size=18),
                    on_click=ChatState.process_question,
                    loading=ChatState.is_streaming,
                    color_scheme="blue",
                ),
                width="100%",
                padding_top="1em",
            ),

            # Status indicator
            rx.cond(
                ChatState.is_streaming,
                rx.hstack(
                    rx.spinner(size="1"),
                    rx.text("AI is thinking...", size="1", color="gray"),
                    spacing="2",
                    margin_top="0.5em",
                ),
            ),

            width="100%",
        ),
        width="100%",
        height="100%",
    )
