"""
Chat component - Conversational interface with streaming responses.
"""
import reflex as rx
from ..state.chat_state import ChatState


def message_bubble(msg: dict) -> rx.Component:
    """Render a single chat message with avatar."""
    is_user = msg["role"] == "user"
    return rx.cond(
        is_user,
        # ─── User Message ───
        rx.hstack(
            rx.spacer(),
            rx.vstack(
                rx.box(
                    rx.markdown(msg["content"]),
                    color="white",
                ),
                background=rx.color("orange", 9),
                border_radius="16px 16px 0 16px",
                padding="0.75em 1em",
                max_width="80%",
            ),
            rx.avatar(
                fallback="👤",
                size="2",
                color_scheme="gray",
            ),
            align="end",
            width="100%",
            spacing="3",
        ),
        # ─── AI Message ───
        rx.hstack(
            rx.avatar(
                fallback="🤖",
                size="2",
                color_scheme="orange",
            ),
            rx.vstack(
                rx.box(
                    rx.markdown(msg["content"]),
                    color=rx.color_mode_cond(
                        light=rx.color("slate", 12),
                        dark=rx.color("slate", 11),
                    ),
                ),
                background=rx.color_mode_cond(
                    light=rx.color("slate", 2),
                    dark=rx.color("slate", 3),
                ),
                border_radius="0 16px 16px 16px",
                padding="0.75em 1em",
                max_width="80%",
                border=f"1px solid {rx.color_mode_cond(light=rx.color('slate', 4), dark='rgba(255,255,255,0.06)')}",
            ),
            align="start",
            width="100%",
            spacing="3",
        ),
    )


def welcome_state() -> rx.Component:
    """Welcome screen when no messages exist."""
    return rx.vstack(
        rx.box(
            rx.icon("bot", size=64, color="orange"),
            padding="1em",
            border_radius="full",
            background=rx.color_mode_cond(
                light=rx.color("orange", 2),
                dark=rx.color("orange", 3),
            ),
        ),
        rx.heading("RAG AI Assistant", size="6", weight="bold"),
        rx.text(
            "Upload documents and ask me anything about them.",
            color="gray",
            size="3",
            text_align="center",
        ),
        rx.text(
            "I can summarize, extract tables, analyze images, and answer questions.",
            color="gray",
            size="2",
            text_align="center",
        ),
        width="100%",
        height="100%",
        align="center",
        justify="center",
        spacing="4",
    )


def chat_interface() -> rx.Component:
    """Main chat interface with history and input."""
    return rx.card(
        rx.vstack(
            # ─── Header ───
            rx.hstack(
                rx.hstack(
                    rx.icon("bot", size=20, color="orange"),
                    rx.heading("Knowledge Assistant", size="4"),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                rx.button(
                    rx.hstack(
                        rx.icon("trash-2", size=14),
                        rx.text("Clear Chat", size="1"),
                        spacing="2",
                    ),
                    on_click=ChatState.clear_history,
                    variant="soft",
                    color_scheme="red",
                    size="1",
                ),
                width="100%",
                align="center",
                padding_bottom="0.5em",
            ),

            rx.divider(),

            # ─── Chat Area ───
            rx.box(
                rx.cond(
                    ChatState.chat_history.length() == 0,
                    welcome_state(),
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(
                                ChatState.chat_history,
                                message_bubble,
                            ),
                            width="100%",
                            padding="0.5em",
                            spacing="3",
                        ),
                        height="calc(100dvh - 280px)",
                        width="100%",
                        scrollbars="vertical",
                    ),
                ),
                flex="1",
                width="100%",
                min_height="0",
            ),

            rx.divider(),

            # ─── Input Area (Fixed Bottom) ───
            rx.hstack(
                rx.input(
                    placeholder="Ask about your documents...",
                    value=ChatState.current_question,
                    on_change=ChatState.set_question,
                    on_key_down=ChatState.handle_key_down,
                    size="3",
                    border_radius="full",
                    flex="1",
                    border_color=rx.color_mode_cond(
                        light=rx.color("slate", 6),
                        dark="rgba(255,255,255,0.1)",
                    ),
                ),
                rx.icon_button(
                    rx.icon("send", size=18),
                    on_click=ChatState.process_question,
                    loading=ChatState.is_streaming,
                    color_scheme="orange",
                    size="3",
                    radius="full",
                ),
                width="100%",
                spacing="2",
                padding_top="0.5em",
            ),

            # ─── Status ───
            rx.cond(
                ChatState.is_streaming,
                rx.hstack(
                    rx.spinner(size="2", color="orange"),
                    rx.text("AI is thinking...", size="1", color="gray"),
                    spacing="2",
                ),
            ),

            width="100%",
            height="100%",
            spacing="2",
        ),
        width="100%",
        height="100%",
        variant="surface",
    )
