import reflex as rx
import asyncio
import base64
from io import BytesIO
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Import our backend logic
from backend.document_processor import DocumentProcessor
from backend.vectorstore import VectorStoreManager
from backend.agent import create_documentation_agent
from backend.tools import create_search_tool
from backend.structure_visualizer import DocumentStructureVisualizer

load_dotenv()


class State(rx.State):
    """The application state."""
    
    # --- UI Vars ---
    uploaded_filenames: List[str] = []
    processing_status: str = "Ready"
    is_processing: bool = False
    
    # Chat State
    messages: List[Dict[str, str]] = []
    question: str = ""
    is_chatting: bool = False

    # Visualization State
    doc_options: List[str] = []
    selected_doc: str = ""
    viz_summary: Dict[str, Any] = {}
    viz_hierarchy: List[Dict[str, Any]] = []
    viz_tables: List[Dict[str, Any]] = []
    viz_images: List[Dict[str, Any]] = []

    # --- Backend Vars (Private) ---
    _docling_docs: List[Any] = []
    _vectorstore: Any = None
    _agent: Any = None
    _config: Dict = {"configurable": {"thread_id": "reflex_chat"}}

    # --- File Upload Logic ---
    @rx.event
    async def handle_upload(self, files: List[rx.UploadFile]):
        """Handle async file upload and save to disk."""
        print(f"🔵 handle_upload called with {len(files)} files")
        self.is_processing = True
        self.processing_status = "Uploading..."
        
        upload_dir = rx.get_upload_dir()
        print(f"📁 Upload directory: {upload_dir}")
        saved_paths = []
        
        for file in files:
            print(f"📄 Processing file: {file.filename}")
            upload_data = await file.read()
            outfile = upload_dir / file.filename
            with open(outfile, "wb") as f:
                f.write(upload_data)
            saved_paths.append(str(outfile))
            self.uploaded_filenames.append(file.filename)
            print(f"✅ Saved: {file.filename}")
        
        print(f"🚀 Starting background processing for {len(saved_paths)} files")
        # Start processing in background
        return State.process_and_index(saved_paths)

    @rx.event(background=True)
    async def process_and_index(self, file_paths: List[str]):
        """Background task to process documents."""
        print(f"🔄 Background processing started for: {file_paths}")
        async with self:
            self.processing_status = "Processing with Docling (OCR)..."

        try:
            # 1. Process
            print("📝 Starting document processing...")
            processor = DocumentProcessor()
            documents, docling_docs = await asyncio.to_thread(
                processor.process_files, file_paths
            )
            print(f"✅ Processed {len(documents)} documents")
            
            async with self:
                self._docling_docs = docling_docs
                # Update visualizer options
                self.doc_options = list(set([b['base_filename'] for b in docling_docs]))
                if self.doc_options:
                    self.selected_doc = self.doc_options[0]
                self.processing_status = "Creating Vector Store..."
                print(f"📊 Document options: {self.doc_options}")

            # 2. Vector Store
            print("🗄️ Creating vector store...")
            vs_manager = VectorStoreManager()
            chunks = await asyncio.to_thread(vs_manager.chunk_documents, documents)
            vectorstore = await asyncio.to_thread(vs_manager.create_vectorstore, chunks)
            print(f"✅ Vector store created with {len(chunks)} chunks")

            # 3. Agent
            print("🤖 Creating agent...")
            search_tool = create_search_tool(vectorstore)
            agent = create_documentation_agent([search_tool])

            async with self:
                self._vectorstore = vectorstore
                self._agent = agent
                self.processing_status = "✅ Ready to chat!"
                self.is_processing = False
                print("🎉 Processing complete!")
                
            # Trigger visualization update for the default selected doc
            await self.update_visualizer()

        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            async with self:
                self.processing_status = f"Error: {str(e)}"
                self.is_processing = False

    # --- Visualization Logic ---
    @rx.event
    async def update_visualizer(self):
        """Prepare data for the visualizer tab based on selection."""
        if not self.selected_doc or not self._docling_docs:
            return

        # Filter batches for the selected document
        batches = [b for b in self._docling_docs if b['base_filename'] == self.selected_doc]
        viz = DocumentStructureVisualizer(batches)

        # 1. Summary & Hierarchy (Simple Data)
        self.viz_summary = viz.get_document_summary()
        self.viz_hierarchy = viz.get_document_hierarchy()

        # 2. Tables (Convert DataFrames to List of Dicts for Reflex)
        raw_tables = viz.get_tables_info()
        clean_tables = []
        for t in raw_tables:
            if not t['is_empty']:
                # Convert DF to records for rx.data_table
                t['data'] = t['dataframe'].astype(str).to_dict('records')
                t['columns'] = [{"title": col, "id": col} for col in t['dataframe'].columns]
                del t['dataframe'] # Remove non-serializable object
                clean_tables.append(t)
        self.viz_tables = clean_tables

        # 3. Images (Convert PIL to Base64)
        raw_pics = viz.get_pictures_info()
        clean_pics = []
        for p in raw_pics:
            if p['pil_image']:
                buffered = BytesIO()
                p['pil_image'].save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                p['src'] = f"data:image/png;base64,{img_str}"
                del p['pil_image'] # Remove non-serializable object
                clean_pics.append(p)
        self.viz_images = clean_pics

    # --- Setter Methods ---
    def set_question(self, value: str):
        """Set the question input."""
        self.question = value
    
    def set_selected_doc(self, value: str):
        """Set the selected document and update visualizer."""
        self.selected_doc = value
        return State.update_visualizer

    # --- Chat Logic ---
    @rx.event(background=True)
    async def handle_submit(self):
        """Handle chat submission with streaming."""
        async with self:
            if not self.question or not self._agent:
                return
            
            user_input = self.question
            self.messages.append({"role": "user", "content": user_input})
            self.messages.append({"role": "assistant", "content": ""}) # Placeholder
            self.question = ""
            self.is_chatting = True

        try:
            input_msg = HumanMessage(content=user_input)
            response_content = ""

            # Stream response from LangGraph agent
            async for event in self._agent.astream_events(
                {"messages": [input_msg]}, 
                config=self._config, 
                version="v1"
            ):
                kind = event["event"]
                # Only capture the stream from the chat model
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        response_content += content
                        async with self:
                            self.messages[-1]["content"] = response_content

        except Exception as e:
            async with self:
                self.messages.append({"role": "system", "content": f"Error: {str(e)}"})
        
        async with self:
            self.is_chatting = False
