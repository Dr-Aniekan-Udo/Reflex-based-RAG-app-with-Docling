"""
Enterprise RAG Application - Main entry point.
"""
import reflex as rx
from .pages import dashboard


# Initialize the app with custom theme
app = rx.App(
    theme=rx.theme(
        appearance="light",
        accent_color="blue",
        radius="large",
    ),
)

# Register pages
app.add_page(
    dashboard.index,
    route="/",
    title="Enterprise RAG Dashboard",
    description="A modular Reflex application for intelligent document analysis.",
)
