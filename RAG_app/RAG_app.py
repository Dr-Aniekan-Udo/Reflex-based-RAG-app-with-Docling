"""
Enterprise RAG Application - Main entry point.
"""
from dotenv import load_dotenv
load_dotenv()

import reflex as rx
from .pages import dashboard
from .state.base_state import BaseState
from .core.logging_config import logger

# Initialize logging
logger.info("app_starting")

# Initialize the app (theme configured in rxconfig.py via RadixThemesPlugin)
app = rx.App()

# Register pages
app.add_page(
    dashboard.index,
    route="/",
    on_load=BaseState.on_load,
)
