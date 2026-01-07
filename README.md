# RAG Application - Reflex Version

A production-ready, scalable Document Intelligence Assistant built with Reflex, Docling, LangGraph, and Google Gemini. This application transforms your documents into an intelligent, conversational AI system with advanced document analysis capabilities.

## 🎯 Key Features

### 📄 **Advanced Document Processing**

- Multi-format support (PDF with focus on quality processing)
- **Batched Memory Management** - Handles large files without memory crashes
- **Context-Aware Overlap** - Preserves semantic meaning across page boundaries
- **OCR Support** - Extracts text from scanned documents
- **Table Extraction** - Intelligent table structure recognition
- **Image Detection** - Identifies and catalogs images with metadata

### 💬 **Intelligent Chat Interface**

- Real-time streaming responses
- Conversation memory across sessions
- Source citations with page numbers
- Non-blocking async operations

### 📊 **Document Structure Visualization**

- **Summary View** - Overview statistics and content types
- **Hierarchy View** - Document outline and heading structure
- **Tables View** - Interactive table extraction and display
- **Images View** - Picture metadata with positioning information

### ⚡ **Enterprise Architecture**

- **Async/Await** - Non-blocking operations throughout
- **Background Tasks** - Heavy processing doesn't freeze the UI
- **Singleton Services** - Efficient resource management
- **State Management** - Type-safe, modular state architecture
- **WebSocket Communication** - Real-time bidirectional updates

## 🏗️ Architecture

This application follows a modular, enterprise-grade architecture:

```
enterprise_rag_app/
├── assets/                      # Static files
│   └── styles.css
├── enterprise_rag_app/
│   ├── __init__.py
│   ├── enterprise_rag_app.py   # App entry point
│   ├── components/             # Reusable UI components
│   │   ├── layout.py
│   │   ├── chat.py
│   │   ├── upload.py
│   │   └── structure.py
│   ├── pages/                  # Page views
│   │   └── dashboard.py
│   ├── state/                  # Business logic
│   │   ├── base.py
│   │   ├── chat_state.py
│   │   ├── process_state.py
│   │   └── structure_state.py
│   └── services/               # External integrations
│       ├── vector_store.py
│       └── llm_service.py
├── rxconfig.py                 # Reflex configuration
├── requirements.txt
└── .env
```

### Architecture Highlights

**State Layer**

- `BaseState`: Shared application state
- `ProcessState`: Document processing with background tasks
- `ChatState`: Conversation management with streaming
- `StructureState`: Document analysis and visualization

**Services Layer**

- `VectorStoreService`: Singleton for Chroma vector store and Docling processing
- `LLMService`: Singleton for LangGraph agent with Gemini

**Components Layer**

- Atomic, reusable UI components
- Separation of presentation and logic
- Type-safe props and state binding

## 🚀 Installation

### Prerequisites

- Python 3.10+
- Google Gemini API key

### Step 1: Clone and Setup

```bash
# Clone or extract the project
git clone <repo_name>
cd <repo_name>

# Create virtual environment. If you are using uv ignore this and go to uv sync
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### Step 2: Install Dependencies

**Important**: Install PyTorch CPU version first to avoid GPU bloat:

```bash
pip install torch==2.5.1+cpu torchvision==0.20.1+cpu --index-url https://download.pytorch.org/whl/cpu
```

Then install remaining dependencies:

```bash
pip install -r requirements.txt
```

**For uv users**:

```bash
uv sync
```

### Step 3: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your Google API key
# GOOGLE_API_KEY=your_actual_api_key_here
```

## 🎮 Usage

### Starting the Application

```bash
# Initialize Reflex (first time only)
reflex init
# or
uv run reflex init

# Run the development server
reflex run
# or
uv run reflex run
```

The application will be available at:

- Frontend: http://localhost:3001
- Backend API: http://localhost:8002

### Using the Application

1. **Upload Documents**
   - Navigate to the Chat Interface tab
   - Click "Select Documents" or drag and drop PDF files
   - Click "Upload Files" to upload
   - Click "Process & Vectorize" to process documents

2. **Chat with Documents**
   - Wait for processing to complete (progress bars will show status)
   - Type your question in the chat input
   - Press Enter or click Send
   - Receive streaming responses with source citations

3. **Analyze Document Structure**
   - Switch to the "Document Analysis" tab
   - Select a document from the dropdown
   - Explore different views:
     - Summary: Statistics and content types
     - Hierarchy: Document outline
     - Tables: Extracted tables
     - Images: Image metadata

4. **Clear and Reset**
   - Click "Clear All" to remove all documents and start fresh
   - Click "Clear History" to reset the conversation

## 🔧 Configuration

### Reflex Configuration (rxconfig.py)

Already configured with your provided settings:

```python
config = rx.Config(
    app_name="RAG_app",
    telemetry_enabled=False,
    frontend_port=3001,
    backend_port=8002,
    timeout=600,
    db_url="sqlite:///reflex.db",
)
```

### Environment Variables

- `GOOGLE_API_KEY`: Your Google Gemini API key (required)
- `GEMINI_MODEL`: Model name (default: gemini-2.0-flash-exp)
- `EMBEDDING_MODEL`: Embedding model (default: models/text-embedding-004)

## 🧪 Development

### Project Structure Explained

**Services (Singleton Pattern)**
- Services use the singleton pattern to share resources across all users
- Vector store and LLM instances are created once and reused
- This prevents loading models multiple times and saves memory

**State Management**
- Each user gets their own state instance
- State classes inherit from `rx.State`
- Use `@rx.event` for event handlers
- Use `@rx.event(background=True)` for heavy operations

**Background Tasks**
- Document processing runs in the background
- Progress updates are pushed to the UI via WebSocket
- UI remains responsive during heavy operations

### Adding New Features

1. **New State**: Create a new state class in `state/`
2. **New Component**: Create a component function in `components/`
3. **New Page**: Add a page function in `pages/` and register in `enterprise_rag_app.py`
4. **New Service**: Add service logic in `services/` with singleton pattern

## 📊 Performance Considerations

### Memory Management
- Documents are processed in 50-page batches
- PyTorch CPU version reduces memory footprint
- Singleton services prevent duplicate resource loading

### Concurrency
- Async/await for I/O operations
- `run_in_executor` for CPU-bound operations
- Background tasks for long-running processes

### Scalability
- Stateless backend (except for singleton services)
- WebSocket for efficient real-time updates
- Chroma vector store for fast similarity search

## 🐛 Troubleshooting

### "Agent not initialized" error
- Ensure you've uploaded and processed documents first
- Check that vectorization completed successfully

### Memory issues with large PDFs
- Files are automatically batched in 50-page chunks
- If still having issues, reduce batch size in `vector_store.py`

### API errors
- Verify your Google API key is correct in `.env`
- Check your API quota and limits

### Port conflicts
- Modify `frontend_port` and `backend_port` in `rxconfig.py`

## 🚀 Deployment

### Production Build

```bash
# Export for production
reflex export

# The build will be in .web/_static/
```

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install PyTorch CPU
RUN pip install torch==2.5.1+cpu torchvision==0.20.1+cpu --index-url https://download.pytorch.org/whl/cpu

# Copy and install requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Initialize Reflex
RUN reflex init

# Expose ports
EXPOSE 3000 8000

# Run application
CMD ["reflex", "run", "--env", "prod"]
```

Build and run:

```bash
docker build -t enterprise-rag .
docker run -p 3000:3000 -p 8000:8000 -e GOOGLE_API_KEY=your_key enterprise-rag
```

## 📝 Key Differences from Streamlit

| Feature | Streamlit | Reflex |
|---------|-----------|--------|
| Execution | Synchronous reruns | Async event-driven |
| State | Session dictionary | Typed state classes |
| Concurrency | Threading (limited) | Asyncio + background tasks |
| Frontend | Generated HTML | Compiled React SPA |
| Styling | Limited CSS | Full CSS/Tailwind support |
| Real-time | Limited | WebSocket bidirectional |

## 🤝 Contributing

This is a production-ready template. Feel free to:
- Add more document formats
- Implement authentication
- Add more visualization types
- Integrate other LLM providers
- Add persistent vector storage

## 📄 License

This project is for educational and demonstration purposes.

## 🙏 Acknowledgments

- **Reflex** - Pure Python web framework
- **Docling** - IBM Research document understanding
- **LangChain/LangGraph** - LLM orchestration
- **Google Gemini** - Language models
- **Chroma** - Vector database

---

**Built with ❤️ using Reflex - The future of Python web development**