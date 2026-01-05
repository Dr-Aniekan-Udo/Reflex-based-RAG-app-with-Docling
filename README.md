```
my_app/
├── assets/
│   └── (images, icons, static files)
│
├── backend/
│   ├── __init__.py
│   ├── agent.py                  # 🤖 LLM / LangGraph agent logic
│   ├── document_processor.py     # 📄 Docling document ingestion
│   ├── structure_visualizer.py   # 🧱 Document structure analysis
│   ├── tools.py                  # 🛠️ Retrieval / search tools 
│   └── vectorstore.py            # 🧠 Vector DB logic
│
├── my_app/
│   ├── __init__.py
│   ├── my_app.py                 # 🚀 Main application entry point
│   └── state.py                  # 🔄 App state & core coordination logic
│
├── requirements.txt              # 📦 Python dependencies
└── rxconfig.py                   # ⚙️ App / framework configuration
```