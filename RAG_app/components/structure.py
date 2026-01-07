"""
Structure visualization component - Document analysis views.
"""
import reflex as rx
from ..state.structure_state import StructureState


def structure_view() -> rx.Component:
    """Document structure visualization with tabs"""
    return rx.vstack(
        rx.heading("📊 Document Structure Analysis", size="6", margin_bottom="0.5em"),

        rx.cond(
            StructureState.available_documents,
            rx.vstack(
                rx.select(
                    StructureState.available_documents,
                    value=StructureState.selected_document,
                    on_change=StructureState.select_document,
                    placeholder="Select a document to analyze",
                    width="100%",
                ),

                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("📝 Summary", value="summary"),
                        rx.tabs.trigger("🗂️ Hierarchy", value="hierarchy"),
                        rx.tabs.trigger("📊 Tables", value="tables"),
                        rx.tabs.trigger("🖼️ Images", value="images"),
                    ),

                    rx.tabs.content(summary_tab(), value="summary"),
                    rx.tabs.content(hierarchy_tab(), value="hierarchy"),
                    rx.tabs.content(tables_tab(), value="tables"),
                    rx.tabs.content(images_tab(), value="images"),

                    default_value="summary",
                    width="100%",
                ),
                width="100%",
                spacing="4",
            ),
            rx.callout(
                "👈 Please upload and process documents first to view their structure!",
                icon="info",
                size="2",
            ),
        ),
        width="100%",
        align="start",
    )


def summary_tab() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Summary", size="4", margin_bottom="1em"),

            rx.grid(
                summary_card("Total Pages", StructureState.current_summary["num_pages"]),
                summary_card("Tables", StructureState.current_summary["num_tables"]),
                summary_card("Images", StructureState.current_summary["num_pictures"]),
                summary_card("Text Items", StructureState.current_summary["num_texts"]),
                columns="4",
                spacing="4",
                width="100%",
            ),

            rx.heading("Content Types", size="3", margin_top="2em", margin_bottom="1em"),
            rx.cond(
                StructureState.text_types_list,
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
                rx.text("No text content detected", size="2", color="gray"),
            ),

            align="start",
            spacing="4",
            width="100%",
        ),
        padding="2em",
    )


def summary_card(title: str, value) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(title, size="1", color="gray"),
            rx.text(value, size="6", weight="bold"),
            align="center",
        ),
    )


def hierarchy_tab() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Document Hierarchy", size="4", margin_bottom="1em"),

            rx.cond(
                StructureState.current_hierarchy,
                rx.vstack(
                    rx.foreach(
                        StructureState.current_hierarchy,
                        lambda item: rx.hstack(
                            rx.box(
                                width=rx.match(
                                    item["level"],
                                    (1, "0em"),
                                    (2, "2em"),
                                    (3, "4em"),
                                    (4, "6em"),
                                    "8em",
                                )
                            ),
                            rx.text(item["text"], size="2", weight=rx.cond(item["level"] == 1, "bold", "regular")),
                            rx.text(" (Page "),
                            rx.text(item["page"]),
                            rx.text(")"),
                            width="100%",
                        ),
                    ),
                    align="start",
                    spacing="2",
                    width="100%",
                ),
                rx.text("No hierarchical structure detected", size="2", color="gray"),
            ),

            align="start",
            spacing="4",
            width="100%",
        ),
        padding="2em",
    )


def tables_tab() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Extracted Tables", size="4", margin_bottom="1em"),

            rx.cond(
                StructureState.current_tables,
                rx.vstack(
                    rx.foreach(
                        StructureState.current_tables,
                        lambda table: rx.card(
                            rx.vstack(
                                rx.hstack(
                                    rx.text("Table "),
                                    rx.text(table["table_number"]),
                                    rx.text(" (Page "),
                                    rx.text(table["page"]),
                                    rx.text(")"),
                                ),
                                rx.cond(
                                    table["caption"],
                                    rx.text(table["caption"], size="1", color="gray"),
                                ),
                                rx.cond(
                                    ~table["is_empty"],
                                    rx.table.root(
                                        rx.table.header(
                                            rx.table.row(
                                                rx.foreach(
                                                    table["columns"],
                                                    lambda col: rx.table.column_header_cell(col),
                                                ),
                                            ),
                                        ),
                                        rx.table.body(
                                            rx.foreach(
                                                table["rows"],
                                                lambda row: rx.table.row(
                                                    rx.foreach(
                                                        row,
                                                        lambda cell: rx.table.cell(cell),
                                                    ),
                                                ),
                                            ),
                                        ),
                                        width="100%",
                                    ),
                                    rx.text("Table is empty", size="2", color="gray"),
                                ),
                                align="start",
                                spacing="2",
                                width="100%",
                            ),
                            width="100%",
                        ),
                    ),
                    align="start",
                    spacing="4",
                    width="100%",
                ),
                rx.text("No tables found in this document", size="2", color="gray"),
            ),

            align="start",
            spacing="4",
            width="100%",
        ),
        padding="2em",
    )


def images_tab() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Extracted Images", size="4", margin_bottom="1em"),

            rx.cond(
                StructureState.current_pictures,
                rx.vstack(
                    rx.foreach(
                        StructureState.current_pictures,
                        lambda pic: rx.card(
                            rx.vstack(
                                rx.hstack(
                                    rx.text("Image "),
                                    rx.text(pic["picture_number"]),
                                    rx.text(" (Page "),
                                    rx.text(pic["page"]),
                                    rx.text(")"),
                                ),
                                rx.cond(
                                    pic["caption"],
                                    rx.text(pic["caption"], size="2", color="gray"),
                                ),
                                rx.cond(
                                    pic["has_image"],
                                    rx.text("📷 Image available", size="2", color="green"),
                                    rx.text("⚠️ Image data not available", size="2", color="gray"),
                                ),
                                rx.cond(
                                    pic["bounding_box"],
                                    rx.vstack(
                                        rx.text("Bounding Box:", size="1", color="gray"),
                                        rx.text(pic["bounding_box"]["left"]),
                                        rx.text(pic["bounding_box"]["top"]),
                                        rx.text(pic["bounding_box"]["right"]),
                                        rx.text(pic["bounding_box"]["bottom"]),
                                    ),
                                ),
                                align="start",
                                spacing="2",
                                width="100%",
                            ),
                            width="100%",
                        ),
                    ),
                    align="start",
                    spacing="4",
                    width="100%",
                ),
                rx.text("No images found in this document", size="2", color="gray"),
            ),

            align="start",
            spacing="4",
            width="100%",
        ),
        padding="2em",
    )
