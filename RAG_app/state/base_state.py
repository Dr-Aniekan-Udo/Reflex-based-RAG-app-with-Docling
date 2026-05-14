import reflex as rx
from ..core.session_registry import get_registry
from ..core.logging_config import logger


class BaseState(rx.State):
    """Base state with session isolation and shared globals."""

    session_id: str = ""
    app_initialized: bool = False

    @rx.event
    def on_load(self):
        """Initialize session on first page load."""
        if not self.session_id:
            registry = get_registry()
            self.session_id = registry.create_session()
            self.app_initialized = True
            logger.info("session_initialized", session_id=self.session_id)
        else:
            logger.info("session_already_exists", session_id=self.session_id)


