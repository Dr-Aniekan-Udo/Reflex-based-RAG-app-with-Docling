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
                                rx.heading(str(StructureState.current_summary.get("num_pages", 0)), size="5"),
                            )
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Tables", size="1", color="gray"),
                                rx.heading(str(StructureState.current_summary.get("num_tables", 0)), size="5"),
                            )
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Images", size="1", color="gray"),
                                rx.heading(str(StructureState.current_summary.get("num_pictures", 0)), size="5"),
                            )
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Text Items", size="1", color="gray"),
                                rx.heading(str(StructureState.current_summary.get("num_texts", 0)), size="5"),
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
                                    rx.table.cell(str(item[0])),
                                    rx.table.cell(str(item[1])),
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
                rx.vstack(
                    rx.foreach(
                        StructureState.current_hierarchy,
                        lambda item: rx.hstack(
                            rx.text(
                                item.get("text", ""),
                                size="2",
                                weight=item.get("weight", "medium"),
                                color=item.get("color", "black"),
                            ),
                            rx.spacer(),
                            rx.text(
                                item.get("page_str", ""),
                                size="1",
                                color="gray",
                            ),
                            width="100%",
                            padding_y="0.25em",
                            border_bottom="1px solid #f0f0f0",
                        ),
                    ),
                ),
                value="hierarchy",
            ),

            # Tables tab
            rx.tabs.content(
                rx.vstack(
                    rx.foreach(
                        StructureState.current_tables,
                        lambda table: rx.vstack(
                            rx.heading(
                                table.get("display_title", ""),
                                size="3",
                            ),
                            rx.cond(
                                table.get("caption") != None,
                                rx.text(table.get("caption", ""), size="1", color="gray"),
                                rx.box(),
                            ),
                            rx.cond(
                                table.get("rows", []).length() > 0,
                                rx.box(
                                    rx.table.root(
                                        rx.table.header(
                                            rx.table.row(
                                                rx.foreach(
                                                    table.get("columns", []),
                                                    lambda col: rx.table.column_header_cell(str(col)),
                                                ),
                                            ),
                                        ),
                                        rx.table.body(
                                            rx.foreach(
                                                table.get("rows", []),
                                                lambda row: rx.table.row(
                                                    rx.foreach(
                                                        table.get("columns", []),
                                                        lambda col: rx.table.cell(str(row.get(col, ""))),
                                                    ),
                                                ),
                                            ),
                                        ),
                                        width="100%",
                                    ),
                                    overflow_x="auto",
                                    max_width="100%",
                                    border="1px solid #e2e8f0",
                                    border_radius="6px",
                                ),
                                rx.text("Table is empty", color="gray"),
                            ),
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
                                pic.get("display_title", ""),
                                size="3",
                            ),
                            rx.cond(
                                pic.get("caption") != None,
                                rx.text(pic.get("caption", ""), size="1", color="gray"),
                                rx.box(),
                            ),
                            rx.cond(
                                pic.get("image_data") != None,
                                rx.image(
                                    src=pic.get("image_data"),
                                    width="100%",
                                    max_width="600px",
                                    border_radius="8px",
                                    box_shadow="sm",
                                ),
                                rx.text("Image data not available", color="gray", size="2"),
                            ),
                            rx.cond(
                                pic.get("bounding_box") != None,
                                rx.box(
                                    rx.text(
                                        pic.get("bbox_text", ""),
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
