# Streamlit to Reflex Migration Guide

This document explains the architectural changes and conversion decisions made when migrating from Streamlit to Reflex.

## 🎯 Core Architectural Shifts

### 1. Execution Model

**Streamlit**: Script reruns top-to-bottom on every interaction

```python
# Streamlit approach
if st.button("Process"):
    result = process_documents()  # Blocks entire script
    st.write(result)
```

**Reflex**: Event-driven state updates

```python
# Reflex approach
@rx.event(background=True)
async def process_documents(self):
    async with self:
        self.status = "Processing..."
    result = await heavy_operation()
    async with self:
        self.result = result
```

### 2. State Management

**Streamlit**: Global dictionary

```python
st.session_state["documents"] = []
st.session_state["processing"] = False
```

**Reflex**: Typed state classes

```python
class ProcessState(rx.State):
    documents: List[str] = []
    processing: bool = False
```

### 3. Concurrency

**Streamlit**: Threading with st.spinner

```python
with st.spinner("Processing..."):
    result = blocking_function()  # UI freezes
```

**Reflex**: Async with background tasks

```python
@rx.event(background=True)
async def process(self):
    async with self:
        self.is_processing = True
    result = await non_blocking_function()  # UI stays responsive
```

## 📊 Component Mapping

### File Upload

**Streamlit**:

```python
uploaded_file = st.file_uploader("Upload PDF")
if uploaded_file:
    bytes_data = uploaded_file.read()
```

**Reflex**:

```python
rx.upload(
    rx.button("Select Files"),
    id="upload_files",
    accept={"application/pdf": [".pdf"]},
)

@rx.event
async def handle_upload(self, files: List[rx.UploadFile]):
    for file in files:
        data = await file.read()
```

### Progress Bars

**Streamlit**:

```python
progress_bar = st.progress(0)
for i in range(100):
    progress_bar.progress(i)
    time.sleep(0.01)
```

**Reflex**:

```python
# In state class
upload_progress: int = 0

# In component
rx.progress(value=ProcessState.upload_progress)

# Update in background task
async with self:
    self.upload_progress = 50
```

### Chat Interface

**Streamlit**:

```python
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Question"):
    response = get_response(prompt)
```

**Reflex**:

```python
# Component
rx.foreach(
    ChatState.chat_history,
    lambda qa: message_bubble(qa)
)

rx.input(
    value=ChatState.current_question,
    on_change=ChatState.set_question,
)

# State with streaming
@rx.event(background=True)
async def process_question(self):
    async for token in llm_stream(question):
        async with self:
            self.chat_history[-1].answer += token
```

### Tabs

**Streamlit**:

```python
tab1, tab2 = st.tabs(["Chat", "Structure"])
with tab1:
    st.write("Chat content")
with tab2:
    st.write("Structure content")
```

**Reflex**:

```python
rx.tabs.root(
    rx.tabs.list(
        rx.tabs.trigger("Chat", value="chat"),
        rx.tabs.trigger("Structure", value="structure"),
    ),
    rx.tabs.content(chat_view(), value="chat"),
    rx.tabs.content(structure_view(), value="structure"),
)
```

## 🔄 Key Pattern Conversions

### Pattern 1: Heavy Processing

**Streamlit**:

```python
with st.spinner("Processing..."):
    documents = processor.process(files)  # Blocks
    vectorstore = create_vectorstore(documents)  # Blocks
st.success("Done!")
```

**Reflex**:

```python
@rx.event(background=True)
async def process(self):
    async with self:
        self.status = "Processing..."
    
    # Offload to executor
    loop = asyncio.get_running_loop()
    documents = await loop.run_in_executor(
        None, processor.process, files
    )
    
    async with self:
        self.status = "Creating vectors..."
    
    vectorstore = await loop.run_in_executor(
        None, create_vectorstore, documents
    )
    
    async with self:
        self.status = "Done!"
```

### Pattern 2: Conditional Rendering

**Streamlit**:

```python
if st.session_state.get("processing"):
    st.spinner("Processing...")
else:
    st.button("Process")
```

**Reflex**:

```python
rx.cond(
    ProcessState.processing,
    rx.spinner(),
    rx.button("Process", on_click=ProcessState.start_processing)
)
```

### Pattern 3: Data Tables

**Streamlit**:

```python
df = pd.DataFrame(data)
st.dataframe(df)
```

**Reflex**:

```python
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.foreach(columns, lambda col: rx.table.column_header_cell(col))
        )
    ),
    rx.table.body(
        rx.foreach(
            data,
            lambda row: rx.table.row(
                rx.foreach(columns, lambda col: rx.table.cell(row[col]))
            )
        )
    )
)
```

## 🏗️ Service Layer (New in Reflex)

To avoid loading heavy models for every user, we use singleton services:

```python
class VectorStoreService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        # Load heavy resources once
        self.embeddings = load_embeddings()
        self._initialized = True

# Usage across all users
def get_vector_store() -> VectorStoreService:
    return VectorStoreService()
```

This prevents the memory bloat that would occur if each user state loaded its own copy of the models.

## 🔌 State Communication

### Accessing Another State

**Streamlit**: Direct dictionary access

```python
st.session_state["key"] = value
other_value = st.session_state["other_key"]
```

**Reflex**: State instantiation

```python
class ChatState(rx.State):
    def use_process_data(self):
        process_state = ProcessState()
        return process_state.documents
```

### Shared Data

**Streamlit**: `@st.cache_resource`

```python
@st.cache_resource
def load_model():
    return HeavyModel()

model = load_model()  # Shared across users
```

**Reflex**: Singleton services

```python
# In services/
class ModelService:
    _instance = None
    # ... singleton pattern

# Usage
model = get_model_service()  # Same instance for all users
```

## ⚡ Performance Optimizations

### Streamlit Bottlenecks

1. **Full script rerun** on every interaction
2. **Blocking operations** freeze UI
3. **Limited concurrency** with threads
4. **No granular updates** - full page refresh

### Reflex Solutions

1. **Event-driven** - only affected state updates
2. **Async/await** - non-blocking operations
3. **Background tasks** - true concurrency
4. **WebSocket deltas** - only changed data sent

### Example: Processing 100 Pages

**Streamlit** (blocks for 30 seconds):

```python
progress = st.progress(0)
for i in range(100):
    result = process_page(i)  # Blocks
    progress.progress(i)
```

**Reflex** (UI responsive throughout):

```python
@rx.event(background=True)
async def process_pages(self):
    loop = asyncio.get_running_loop()
    for i in range(100):
        result = await loop.run_in_executor(None, process_page, i)
        async with self:
            self.progress = i
        await asyncio.sleep(0.01)  # Allow UI update
```

## 🎨 Styling

**Streamlit**: Limited CSS injection

```python
st.markdown("""
<style>
.stButton > button {
    background: blue;
}
</style>
""", unsafe_allow_html=True)
```

**Reflex**: Full CSS support

```python
# In component
rx.button(
    "Click me",
    background="blue",
    _hover={"background": "darkblue"},
    padding="1em",
)

# Or in assets/styles.css
button:hover {
    transform: translateY(-1px);
}
```

## 🚀 Deployment Differences

### Streamlit

- Deploy to Streamlit Cloud (easiest)
- Limited control over infrastructure
- Automatic scaling limited

### Reflex

- Exports to static + ASGI app
- Deploy anywhere (Docker, VPS, Cloud)
- Frontend and backend can scale independently
- Use Nginx for frontend, Gunicorn for backend

## ✅ Migration Checklist

- [ ] Convert script to component functions
- [ ] Create state classes for session_state
- [ ] Implement singleton services for shared resources
- [ ] Convert blocking operations to async
- [ ] Use background tasks for heavy processing
- [ ] Update progress tracking with state
- [ ] Replace st.cond with rx.cond
- [ ] Convert st.foreach to rx.foreach
- [ ] Update styling to Reflex components
- [ ] Test non-blocking behavior
- [ ] Verify memory usage with singleton services

## 📚 Additional Resources

- [Reflex Documentation](https://reflex.dev/docs)
- [Async Python Guide](https://docs.python.org/3/library/asyncio.html)
- [WebSocket Protocol](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)

---

**The result**: A faster, more scalable, production-ready application! 🎉
