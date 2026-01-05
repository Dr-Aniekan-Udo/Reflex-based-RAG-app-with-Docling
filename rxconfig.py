import reflex as rx

config = rx.Config(
    app_name="RAG_app",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
    frontend_port=3001,
    backend_port=8002,
    db_url="sqlite:///reflex.db",
    env_file=rx.Env.DEV,
)
