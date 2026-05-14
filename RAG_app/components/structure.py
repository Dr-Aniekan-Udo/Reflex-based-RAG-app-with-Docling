"""
Structure component - Document analysis tabs.
"""
import reflex as rx
from ..state.structure_state import StructureState


def stat_card(icon_name: str, label: str, value: str, color: str) -> rx.Component:
    """Color-coded stat card for summary."""
    return rx.card(
        rx.hstack(
            rx.icon(icon_name, size=24, color=color),
            rx.vstack(
                rx.text(value, size="5", weight="bold"),
                rx.text(label, size="1", color="gray"),
                spacing="0",
            ),
            spacing="3",
            align="center",
        ),
        padding="1em",
        _hover={
            "transform": "translateY(-4px)",
            "box_shadow": f"0 8px 24px {rx.color(color, 6, alpha=True)}",
        },
        transition="all 0.25s ease",
    )


def structure_view() -> rx.Component:
    """Document structure visualization with tabs."""
    return rx.vstack(
        rx.heading("📊 Document Analysis", size="4", margin_bottom="0.5em"),

        # Document selector
        rx.select(
            StructureState.available_documents,
            value=StructureState.selected_document,
            on_change=StructureState.select_document,
            placeholder="Select a document...",
            width="100%",
            size="3",
            radius="medium",
        ),

        # Tabs
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger(
                    rx.hstack(rx.icon("file-text"), rx.text("Summary"), spacing="2"),
                    value="summary",
                ),
                rx.tabs.trigger(
                    rx.hstack(rx.icon("list-tree"), rx.text("Hierarchy"), spacing="2"),
                    value="hierarchy",
                ),
                rx.tabs.trigger(
                    rx.hstack(rx.icon("table"), rx.text("Tables"), spacing="2"),
                    value="tables",
                ),
                rx.tabs.trigger(
                    rx.hstack(rx.icon("image"), rx.text("Images"), spacing="2"),
                    value="images",
                ),
                justify="center",
                background=rx.color_mode_cond(
                    light=rx.color("slate", 3),
                    dark=rx.color("slate", 3),
                ),
                border_radius="full",
                padding="0.25em",
            ),

            # Summary tab
            rx.tabs.content(
                rx.vstack(
                    rx.grid(
                        stat_card("book-open", "Pages", StructureState.current_summary["num_pages"], "orange"),
                        stat_card("table", "Tables", StructureState.current_summary["num_tables"], "sky"),
                        stat_card("image", "Images", StructureState.current_summary["num_pictures"], "grass"),
                        stat_card("type", "Text Items", StructureState.current_summary["num_texts"], "violet"),
                        columns="4",
                        spacing="4",
                        width="100%",
                    ),
                    rx.heading("Content Types", size="3", margin_top="1em"),
                    rx.card(
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
                        width="100%",
                    ),
                ),
                value="summary",
            ),

            # Hierarchy tab
            rx.tabs.content(
                rx.card(
                    rx.box(
                        rx.html(StructureState.current_hierarchy_html),
                        width="100%",
                        overflow_y="auto",
                    ),
                    width="100%",
                ),
                value="hierarchy",
            ),

            # Tables tab
            rx.tabs.content(
                rx.vstack(
                    rx.foreach(
                        StructureState.current_tables_html,
                        lambda table: rx.card(
                            rx.vstack(
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
                                width="100%",
                            ),
                            width="100%",
                            _hover={
                                "transform": "translateY(-2px)",
                                "box_shadow": "0 8px 24px rgba(234, 88, 12, 0.1)",
                            },
                            transition="all 0.2s ease",
                        ),
                    ),
                    spacing="4",
                    width="100%",
                ),
                value="tables",
            ),

            # Images tab
            rx.tabs.content(
                rx.grid(
                    rx.foreach(
                        StructureState.current_pictures,
                        lambda pic: rx.card(
                            rx.vstack(
                                rx.cond(
                                    pic["has_image_data"],
                                    rx.image(
                                        src=pic["image_data"],
                                        width="100%",
                                        height="200px",
                                        object_fit="cover",
                                        border_radius="medium",
                                    ),
                                    rx.box(
                                        rx.icon("image-off", size=32, color="gray"),
                                        height="200px",
                                        display="flex",
                                        align_items="center",
                                        justify_content="center",
                                    ),
                                ),
                                rx.text(pic["display_title"], size="1", weight="medium"),
                                rx.cond(
                                    pic["has_caption"],
                                    rx.text(pic["caption"], size="1", color="gray"),
                                    rx.box(),
                                ),
                                width="100%",
                            ),
                            padding="0.5em",
                            _hover={
                                "transform": "scale(1.02)",
                                "box_shadow": "0 12px 32px rgba(234, 88, 12, 0.15)",
                            },
                            transition="all 0.25s ease",
                        ),
                    ),
                    columns="3",
                    spacing="4",
                    width="100%",
                ),
                value="images",
            ),

            default_value="summary",
            width="100%",
        ),

        width="100%",
    )
