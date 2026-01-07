"""
Base state for the application.
Provides shared functionality across all states.
"""
import reflex as rx


class BaseState(rx.State):
    """Base state class with shared functionality"""

    # Global metadata
    current_user: str = "Guest User"
    theme_mode: str = "light"

    # App status
    app_initialized: bool = False
 
    def toggle_theme(self):
        """Toggle between light and dark mode"""
        self.theme_mode = "dark" if self.theme_mode == "light" else "light"
