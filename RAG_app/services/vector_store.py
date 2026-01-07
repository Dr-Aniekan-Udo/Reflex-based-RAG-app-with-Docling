"""
Vector store management for document storage and retrieval.
Thread-safe singleton pattern for shared resources.
All file processing happens in-memory without disk writes.
"""
import asyncio
from typing import List, Optional
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from dotenv import load_dotenv

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.document import DocumentStream

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma


class VectorStoreService:
    """Singleton service for vector store operations"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Initialize Docling converter
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = 2.0
        load_dotenv()
        
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        # Initialize embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004"
        )
        
        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=len,
        )
        
        # Vectorstore instance (will be created when documents are processed)
        self.vectorstore: Optional[Chroma] = None
        
        self._initialized = True
    
    async def process_documents(self, file_data: List[tuple]) -> tuple:
        """
        Process uploaded files and create vector store.
        All processing happens in-memory from bytes data.
        
        Args:
            file_data: List of (filename, bytes_data) tuples
            
        Returns:
            Tuple of (documents, docling_docs, success_count, error_count)
        """
        documents = []
        docling_docs = []
        success_count = 0
        error_count = 0
        
        loop = asyncio.get_running_loop()
        
        for filename, file_bytes in file_data:
            try:
                # Process in executor to avoid blocking
                result = await loop.run_in_executor(
                    None,
                    self._process_single_file,
                    filename,
                    file_bytes
                )
                
                if result:
                    docs, docling_doc_list = result
                    documents.extend(docs)
                    docling_docs.extend(docling_doc_list)
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                error_count += 1
        
        return documents, docling_docs, success_count, error_count
    
    def _process_single_file(self, filename: str, file_bytes: bytes):
        """
        Process a single PDF file from memory (blocking operation).
        NO disk writes - everything stays in memory.
        """
        try:
            documents = []
            docling_doc_list = []
            
            # Create BytesIO stream from bytes (in-memory)
            master_bytes = BytesIO(file_bytes)
            reader = PdfReader(master_bytes)
            total_pages = len(reader.pages)
            BATCH_SIZE = 50
            
            last_page_tail = ""
            
            for start_page in range(0, total_pages, BATCH_SIZE):
                end_page = min(start_page + BATCH_SIZE, total_pages)
                
                # Create batch in memory
                writer = PdfWriter()
                for i in range(start_page, end_page):
                    writer.add_page(reader.pages[i])
                
                # Write to BytesIO (in-memory, not disk)
                batch_stream = BytesIO()
                writer.write(batch_stream)
                batch_stream.seek(0)
                
                # Create DocumentStream from in-memory bytes
                source = DocumentStream(
                    name=f"{filename}_batch_{start_page}",
                    stream=batch_stream
                )
                
                try:
                    result = self.converter.convert(source)
                    doc = result.document
                    
                    pages_content = {}
                    
                    # Extract text
                    for item in doc.texts:
                        internal_page_no = item.prov[0].page_no
                        if internal_page_no not in pages_content:
                            pages_content[internal_page_no] = ""
                        
                        if item.label == "section_header":
                            pages_content[internal_page_no] += f"\n## {item.text}\n"
                        elif item.label == "title":
                            pages_content[internal_page_no] += f"\n# {item.text}\n"
                        else:
                            pages_content[internal_page_no] += f"{item.text}\n"
                    
                    # Create documents with overlap
                    for internal_page_no, raw_content in pages_content.items():
                        real_page_number = start_page + internal_page_no
                        
                        if last_page_tail:
                            final_content = f"...{last_page_tail}\n\n{raw_content}"
                        else:
                            final_content = raw_content
                        
                        if len(raw_content) > 300:
                            last_page_tail = raw_content[-300:]
                        else:
                            last_page_tail = raw_content
                        
                        page_doc = Document(
                            page_content=final_content,
                            metadata={
                                "source": filename,
                                "filename": filename,
                                "page": real_page_number,
                                "total_pages": total_pages
                            }
                        )
                        documents.append(page_doc)
                    
                    # Store for visualization
                    docling_doc_list.append({
                        'filename': f"{filename} (Pages {start_page}-{end_page-1})",
                        'doc': doc,
                        'page_offset': start_page
                    })
                    
                except Exception as e:
                    print(f"Batch error at {start_page} for {filename}: {e}")
                    continue
                
                finally:
                    # Clean up in-memory batch stream
                    batch_stream.close()
            
            # Clean up master stream
            master_bytes.close()
            
            return documents, docling_doc_list
            
        except Exception as e:
            print(f"File processing error for {filename}: {e}")
            return None
    
    async def create_vectorstore(self, documents: List[Document]) -> bool:
        """Create vector store from documents"""
        try:
            loop = asyncio.get_running_loop()
            
            # Chunk documents
            chunks = await loop.run_in_executor(
                None,
                self.text_splitter.split_documents,
                documents
            )
            
            # Create vectorstore
            self.vectorstore = await loop.run_in_executor(
                None,
                lambda: Chroma.from_documents(
                    documents=chunks,
                    embedding=self.embeddings,
                    collection_name="documents"
                )
            )
            
            return True
            
        except Exception as e:
            print(f"Vectorstore creation error: {e}")
            return False
    
    async def search(self, query: str, k: int = 8) -> List[Document]:
        """Search the vector store"""
        if not self.vectorstore:
            return []
        
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,
                self.vectorstore.similarity_search,
                query,
                k
            )
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def reset(self):
        """Reset the vector store and clean up resources"""
        if self.vectorstore:
            try:
                # Clean up Chroma collection
                self.vectorstore = None
            except Exception as e:
                print(f"Error cleaning up vectorstore: {e}")
        
        self.vectorstore = None


# Global instance
def get_vector_store() -> VectorStoreService:
    """Get the singleton vector store instance"""
    return VectorStoreService()
