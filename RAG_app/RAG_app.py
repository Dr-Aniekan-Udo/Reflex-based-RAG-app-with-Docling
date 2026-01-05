import reflex as rx
from RAG_app.state import State


def sidebar():
    """The sidebar for file uploads."""
    return rx.box(
        rx.vstack(
            rx.heading("Setup", size="5"),
            rx.divider(margin_y="1em"),
            
            # File Upload
            rx.upload(
                rx.vstack(
                    rx.button("Select Files", color_scheme="blue"),
                    rx.text("Drag and drop files here", size="1"),
                ),
                id="upload1",
                multiple=True,
                accept={"application/pdf": [".pdf"], "text/html": [".html"]},
                border="1px dotted gray",
                padding="1em",
            ),
            
            rx.button(
                "Process & Index",
                on_click=State.handle_upload(rx.upload_files(upload_id="upload1")),
                loading=State.is_processing,
                width="100%",
                margin_top="1em",
            ),
            
            rx.divider(margin_y="1em"),
            rx.text(f"Status: {State.processing_status}", size="2"),
            
            rx.cond(
                State.uploaded_filenames,
                rx.vstack(
                    rx.text("Uploaded:", weight="bold", size="2"),
                    rx.foreach(
                        State.uploaded_filenames,
                        lambda x: rx.text(x, size="1")
                    ),
                    spacing="1"
                )
            ),
            spacing="4",
        ),
        height="100vh",
        width="300px",
        padding="2em",
        background="gray.12",
    )


def chat_bubble(message: dict):
    """Renders a single chat message."""
    return rx.box(
        rx.markdown(message["content"]),
        background=rx.cond(message["role"] == "user", "blue.3", "gray.3"),
        padding="1em",
        border_radius="8px",
        align_self=rx.cond(message["role"] == "user", "flex-end", "flex-start"),
        max_width="80%",
        margin_y="0.5em",
    )


def structure_tab():
    """The document structure visualization tab."""
    return rx.vstack(
        rx.hstack(
            rx.text("Analyze Document:", weight="bold"),
            rx.select(
                State.doc_options,
                value=State.selected_doc,
                on_change=State.set_selected_doc,
            ),
            align_items="center"
        ),
        rx.divider(),
        
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Summary", value="summary"),
                rx.tabs.trigger("Hierarchy", value="hierarchy"),
                rx.tabs.trigger("Tables", value="tables"),
                rx.tabs.trigger("Images", value="images"),
            ),
            
            # 1. Summary
            rx.tabs.content(
                rx.grid(
                    rx.card(
                        rx.vstack(
                            rx.text("Pages", weight="bold", size="2"),
                            rx.text(State.viz_summary.get('num_pages', 0), size="6"),
                        )
                    ),
                    rx.card(
                        rx.vstack(
                            rx.text("Tables", weight="bold", size="2"),
                            rx.text(State.viz_summary.get('num_tables', 0), size="6"),
                        )
                    ),
                    rx.card(
                        rx.vstack(
                            rx.text("Images", weight="bold", size="2"),
                            rx.text(State.viz_summary.get('num_pictures', 0), size="6"),
                        )
                    ),
                    columns="3",
                    spacing="4",
                    width="100%"
                ),
                value="summary",
                padding="1em"
            ),
            
            # 2. Hierarchy
            rx.tabs.content(
                rx.foreach(
                    State.viz_hierarchy,
                    lambda item: rx.text(
                        item['text'], 
                        padding_left=f"{item['level']}em",
                        size="2",
                        padding_y="2px"
                    )
                ),
                value="hierarchy",
                padding="1em",
                height="60vh",
                overflow_y="auto"
            ),
            
            # 3. Tables
            rx.tabs.content(
                rx.foreach(
                    State.viz_tables,
                    lambda t: rx.vstack(
                        rx.heading(f"Table {t['table_number']} (Page {t['page']})", size="3"),
                        rx.data_table(data=t['data'], columns=t['columns']),
                        rx.divider(),
                        margin_bottom="2em",
                        width="100%"
                    )
                ),
                value="tables",
                padding="1em",
                height="60vh",
                overflow_y="auto"
            ),

            # 4. Images
            rx.tabs.content(
                rx.foreach(
                    State.viz_images,
                    lambda p: rx.vstack(
                        rx.image(src=p['src'], max_height="300px"),
                        rx.text(f"Image {p['picture_number']} (Page {p['page']})", size="2"),
                        rx.divider(),
                        margin_bottom="2em"
                    )
                ),
                value="images",
                padding="1em",
                height="60vh",
                overflow_y="auto"
            ),
            
            default_value="summary",
            width="100%"
        ),
        width="100%",
        padding="1em",
        align_items="start"
    )


def index():
    return rx.hstack(
        sidebar(),
        rx.container(
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Chat", value="chat"),
                    rx.tabs.trigger("Document Structure", value="viz"),
                ),
                
                rx.tabs.content(
                    rx.vstack(
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(State.messages, chat_bubble),
                                width="100%",
                            ),
                            height="75vh",
                            width="100%",
                            padding="1em",
                            border="1px solid gray.6",
                            border_radius="8px",
                        ),
                        rx.hstack(
                            rx.input(
                                placeholder="Ask a question...",
                                value=State.question,
                                on_change=State.set_question,
                                width="100%",
                            ),
                            rx.button("Send", on_click=State.handle_submit, loading=State.is_chatting),
                            width="100%",
                        ),
                        height="100%",
                    ),
                    value="chat",
                    padding="1em",
                ),
                
                rx.tabs.content(
                    structure_tab(),
                    value="viz",
                ),
                
                default_value="chat",
                width="100%",
                height="100vh",
            ),
            width="100%",
            padding="0",
        ),
        width="100%",
        spacing="0",
    )


# App Definition
app = rx.App()
app.add_page(index)
