"""
Enterprise RAG Application - Main entry point.
"""
import reflex as rx
from .pages import dashboard
from .state.base_state import BaseState


# Initialize the app (theme configured in rxconfig.py via RadixThemesPlugin)
app = rx.App()

# Register pages
app.add_page(
    dashboard.index,
    route="/",
    title="Enterprise RAG Dashboard",
    description="A modular Reflex application for intelligent document analysis.",
    on_load=BaseState.on_load,
)
