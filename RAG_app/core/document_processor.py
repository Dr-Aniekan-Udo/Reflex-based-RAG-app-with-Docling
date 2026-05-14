"""
Docling integration for processing uploaded documents.
Supports PDF, DOCX, PPTX, and HTML.
PDFs are batched in-memory to avoid loading huge files at once.
"""
import os
from io import BytesIO
from typing import List, Tuple, Any

from pypdf import PdfReader, PdfWriter
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.document import DocumentStream
from langchain_core.documents import Document


class DocumentProcessor:
    """Handles document processing using Docling."""

    def __init__(self):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = 2.0

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )

    def process_uploaded_files(self, file_data: List[Tuple[str, bytes]]) -> Tuple[List[Document], List[Any]]:
        """
        Process a list of (filename, bytes) tuples.
        Returns (langchain_documents, docling_docs).
        """
        documents = []
        docling_docs = []

        for filename, file_bytes in file_data:
            print(f"📄 Processing {filename}...")
            ext = os.path.splitext(filename)[1].lower()

            try:
                if ext == ".pdf":
                    docs, ddocs = self._process_pdf(filename, file_bytes)
                elif ext in (".docx", ".pptx", ".html", ".htm"):
                    docs, ddocs = self._process_single_stream(filename, file_bytes, ext)
                else:
                    docs, ddocs = self._process_single_stream(filename, file_bytes, ext)

                documents.extend(docs)
                docling_docs.extend(ddocs)
            except Exception as e:
                print(f"❌ Error processing {filename}: {e}")
                continue

        return documents, docling_docs

    def _process_pdf(self, filename: str, file_bytes: bytes) -> Tuple[List[Document], List[Any]]:
        documents = []
        docling_docs = []
        last_page_tail = ""

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
            source = DocumentStream(name=f"{filename}_batch_{start_page}", stream=batch_stream)

            try:
                result = self.converter.convert(source)
                doc = result.document

                pages_content = {}
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
                            "total_pages": total_pages,
                        }
                    )
                    documents.append(page_doc)

                docling_docs.append({
                    'filename': f"{filename} (Pages {start_page}-{end_page})",
                    'doc': doc,
                    'page_offset': start_page
                })

            except Exception as e:
                print(f"   ⚠️ Error on batch {start_page}: {e}")
                continue

        master_bytes.close()
        return documents, docling_docs

    def _process_single_stream(self, filename: str, file_bytes: bytes, ext: str) -> Tuple[List[Document], List[Any]]:
        stream = BytesIO(file_bytes)

        fmt_map = {
            ".docx": InputFormat.DOCX,
            ".pptx": InputFormat.PPTX,
            ".html": InputFormat.HTML,
            ".htm": InputFormat.HTML,
        }
        input_format = fmt_map.get(ext, InputFormat.HTML)

        source = DocumentStream(name=filename, stream=stream)

        try:
            result = self.converter.convert(source)
            doc = result.document

            pages_content = {}
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

            documents = []
            total_pages = len(getattr(doc, 'pages', {})) or 1

            for internal_page_no, raw_content in pages_content.items():
                real_page_number = internal_page_no
                page_doc = Document(
                    page_content=raw_content,
                    metadata={
                        "source": filename,
                        "filename": filename,
                        "page": real_page_number,
                        "total_pages": total_pages,
                    }
                )
                documents.append(page_doc)

            docling_docs = [{
                'filename': filename,
                'doc': doc,
                'page_offset': 0
            }]

            return documents, docling_docs

        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
            return [], []
