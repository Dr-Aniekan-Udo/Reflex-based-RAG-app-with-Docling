"""
Structure component - Document analysis tabs.
"""
import reflex as rx
from ..state.structure_state import StructureState


def structure_view() -> rx.Component:
    """Document structure visualization with tabs."""
    return rx.vstack(
        rx.heading("📊 Document Analysis", size="4", margin_bottom="1em"),

        # Document selector
        rx.select(
            StructureState.available_documents,
            value=StructureState.selected_document,
            on_change=StructureState.select_document,
            placeholder="Select a document...",
            width="100%",
        ),

        # Tabs
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("📑 Summary", value="summary"),
                rx.tabs.trigger("🏗️ Hierarchy", value="hierarchy"),
                rx.tabs.trigger("📊 Tables", value="tables"),
                rx.tabs.trigger("🖼️ Images", value="images"),
            ),

            # Summary tab
            rx.tabs.content(
                rx.vstack(
                    rx.grid(
                        rx.card(
                            rx.vstack(
                                rx.text("Pages", size="1", color="gray"),
                                rx.heading(StructureState.current_summary["num_pages"], size="5"),
                            )
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Tables", size="1", color="gray"),
                                rx.heading(StructureState.current_summary["num_tables"], size="5"),
                            )
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Images", size="1", color="gray"),
                                rx.heading(StructureState.current_summary["num_pictures"], size="5"),
                            )
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Text Items", size="1", color="gray"),
                                rx.heading(StructureState.current_summary["num_texts"], size="5"),
                            )
                        ),
                        columns="4",
                        spacing="4",
                        width="100%",
                    ),
                    rx.heading("Content Types", size="3", margin_top="1em"),
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Type"),
                                rx.table.column_header_cell("Count"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(
                                StructureState.text_types_list,
                                lambda item: rx.table.row(
                                    rx.table.cell(item[0]),
                                    rx.table.cell(item[1]),
                                ),
                            ),
                        ),
                        width="100%",
                    ),
                ),
                value="summary",
            ),

            # Hierarchy tab
            rx.tabs.content(
                rx.box(
                    rx.html(StructureState.current_hierarchy_html),
                    width="100%",
                    overflow_y="auto",
                ),
                value="hierarchy",
            ),

            # Tables tab
            rx.tabs.content(
                rx.vstack(
                    rx.foreach(
                        StructureState.current_tables_html,
                        lambda table: rx.vstack(
                            rx.heading(
                                table["display_title"],
                                size="3",
                            ),
                            rx.cond(
                                table["has_caption"],
                                rx.text(table["caption"], size="1", color="gray"),
                                rx.box(),
                            ),
                            rx.html(table["html"]),
                            rx.divider(margin_y="1em"),
                        ),
                    ),
                ),
                value="tables",
            ),

            # Images tab
            rx.tabs.content(
                rx.vstack(
                    rx.foreach(
                        StructureState.current_pictures,
                        lambda pic: rx.vstack(
                            rx.heading(
                                pic["display_title"],
                                size="3",
                            ),
                            rx.cond(
                                pic["has_caption"],
                                rx.text(pic["caption"], size="1", color="gray"),
                                rx.box(),
                            ),
                            rx.cond(
                                pic["has_image_data"],
                                rx.image(
                                    src=pic["image_data"],
                                    width="100%",
                                    max_width="600px",
                                    border_radius="8px",
                                    box_shadow="sm",
                                ),
                                rx.text("Image data not available", color="gray", size="2"),
                            ),
                            rx.cond(
                                pic["has_bbox"],
                                rx.box(
                                    rx.text(
                                        pic["bbox_text"],
                                        size="1",
                                        color="gray",
                                    ),
                                    margin_top="0.5em",
                                ),
                                rx.box(),
                            ),
                            rx.divider(margin_y="1em"),
                        ),
                    ),
                ),
                value="images",
            ),

            default_value="summary",
            width="100%",
        ),

        width="100%",
    )
