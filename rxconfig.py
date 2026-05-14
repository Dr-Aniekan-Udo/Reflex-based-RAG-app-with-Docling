import os
import reflex as rx

# Detect GitHub Codespaces and set the correct backend API URL
codespace_name = os.environ.get("CODESPACE_NAME")
if codespace_name:
    api_url = f"https://{codespace_name}-8002.app.github.dev"
else:
    api_url = "http://localhost:8002"

config = rx.Config(
    app_name="RAG_app",
    telemetry_enabled=False,
    api_url=api_url,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="light",
                accent_color="blue",
                radius="large",
            )
        ),
    ],
    frontend_port=3001,
    backend_port=8002,
    timeout=600,
    db_url="sqlite:///reflex.db",
    env_file=rx.Env.DEV,
)
