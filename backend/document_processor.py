"""
Docling integration for processing uploaded documents.
"""

import os
from typing import List, Any, Tuple
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.document import DocumentStream
from langchain_core.documents import Document


class DocumentProcessor:
    def __init__(self):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = 2.0

        self.converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )

    # Adapted to accept file paths (strings) instead of Streamlit UploadedFile objects
    def process_files(self, file_paths: List[str]) -> Tuple[List[Document], List[Any]]:
        documents = []
        docling_docs = []

        for path in file_paths:
            filename = os.path.basename(path)
            print(f"📄 Processing {filename}...")
            
            last_page_tail = ""
            
            try:
                # Read file bytes from disk
                with open(path, "rb") as f:
                    file_bytes = f.read()
                
                master_bytes = BytesIO(file_bytes)
                reader = PdfReader(master_bytes)
                total_pages = len(reader.pages)
                BATCH_SIZE = 50

                for start_page in range(0, total_pages, BATCH_SIZE):
                    end_page = min(start_page + BATCH_SIZE, total_pages)
                    
                    writer = PdfWriter()
                    for i in range(start_page, end_page):
                        writer.add_page(reader.pages[i])
                    
                    batch_stream = BytesIO()
                    writer.write(batch_stream)
                    batch_stream.seek(0)
                    source = DocumentStream(name=f"batch_{start_page}", stream=batch_stream)

                    try:
                        result = self.converter.convert(source)
                        doc = result.document
                        
                        pages_content = {}

                        for item in doc.texts:
                            internal_page_no = item.prov.page_no
                            if internal_page_no not in pages_content:
                                pages_content[internal_page_no] = ""
                            
                            if item.label == "section_header":
                                pages_content[internal_page_no] += f"\n## {item.text}\n"
                            elif item.label == "title":
                                pages_content[internal_page_no] += f"\n# {item.text}\n"
                            else:
                                pages_content[internal_page_no] += f"{item.text}\n"

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

                        docling_docs.append({
                            'filename': f"{filename} (Pages {start_page}-{end_page})",
                            'doc': doc,
                            'page_offset': start_page,
                            'base_filename': filename  # Helper for grouping
                        })

                    except Exception as e:
                        print(f"   ⚠️ Error on batch {start_page}: {str(e)}")
                        continue

            except Exception as e:
                print(f"❌ Error processing {filename}: {str(e)}")
                continue

        return documents, docling_docs
