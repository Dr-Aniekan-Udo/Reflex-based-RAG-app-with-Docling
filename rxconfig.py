import reflex as rx

config = rx.Config(
    app_name="RAG_app",
    telemetry_enabled=False,
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
