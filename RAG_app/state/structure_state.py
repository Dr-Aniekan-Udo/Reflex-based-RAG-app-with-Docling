"""
Structure state for document visualization.
Handles extraction and organization of document structure from Docling.
"""
import reflex as rx
from typing import List, Dict, Any, TypedDict, Optional
from ..state.process_state import ProcessState


class TableInfo(TypedDict):
    table_number: int
    page: Optional[int]
    caption: Optional[str]
    columns: List[str]
    rows: List[List[str]]
    shape: Any
    is_empty: bool


class PictureInfo(TypedDict):
    picture_number: int
    page: Optional[int]
    caption: Optional[str]
    has_image: bool
    bounding_box: Optional[Dict[str, float]]


class HierarchyItem(TypedDict):
    type: str
    text: str
    page: Optional[int]
    level: int


class StructureState(rx.State):
    """State for document structure visualization"""
    
    selected_document: str = ""
    available_documents: List[str] = []
    
    current_summary: Dict[str, Any] = {}
    current_hierarchy: List[HierarchyItem] = []
    current_tables: List[TableInfo] = []
    current_pictures: List[PictureInfo] = []
    
    @rx.var
    def text_types_list(self) -> List[tuple]:
        text_types = self.current_summary.get("text_types", {})
        return sorted(text_types.items(), key=lambda x: -x[1])
    
    @rx.event
    async def load_available_documents(self):
        """Extract unique document names from docling_docs"""
        process_state = await self.get_state(ProcessState)
        
        if not process_state.docling_docs:
            self.available_documents = []
            return
        
        # Extract base filenames
        unique_files = set()
        for batch in process_state.docling_docs:
            filename = batch['filename']
            if " (Pages" in filename:
                base_name = filename.split(" (Pages")[0]
            else:
                base_name = filename
            unique_files.add(base_name)
        
        self.available_documents = sorted(list(unique_files))
        
        # Auto-select first document
        if self.available_documents and not self.selected_document:
            self.selected_document = self.available_documents[0]
            self.load_document_structure()
    
    @rx.event
    def select_document(self, filename: str):
        """Select a document to view"""
        self.selected_document = filename
        self.load_document_structure()
    
    @rx.event
    async def load_document_structure(self):
        """Load structure for selected document"""
        if not self.selected_document:
            return
        
        process_state = await self.get_state(ProcessState)
        
        # Get all batches for this document
        selected_batches = []
        for batch in process_state.docling_docs:
            full_name = batch['filename']
            if " (Pages" in full_name:
                base_name = full_name.split(" (Pages")[0]
            else:
                base_name = full_name
            
            if base_name == self.selected_document:
                selected_batches.append(batch)
        
        if not selected_batches:
            return
        
        # Extract structure
        self.current_summary = self._get_summary(selected_batches)
        self.current_hierarchy = self._get_hierarchy(selected_batches)
        self.current_tables = self._get_tables(selected_batches)
        self.current_pictures = self._get_pictures(selected_batches)
    
    def _get_summary(self, batches: List[Dict]) -> Dict[str, Any]:
        """Extract document summary"""
        total_pages = 0
        total_texts = 0
        total_tables = 0
        total_pictures = 0
        text_types = {}
        
        for batch in batches:
            doc = batch['doc']
            
            pages = getattr(doc, 'pages', {})
            total_pages += len(pages) if pages else 0
            
            texts = getattr(doc, 'texts', [])
            tables = getattr(doc, 'tables', [])
            pictures = getattr(doc, 'pictures', [])
            
            total_texts += len(texts)
            total_tables += len(tables)
            total_pictures += len(pictures)
            
            for item in texts:
                label = getattr(item, 'label', 'unknown')
                text_types[label] = text_types.get(label, 0) + 1
        
        return {
            'num_pages': total_pages,
            'num_texts': total_texts,
            'num_tables': total_tables,
            'num_pictures': total_pictures,
            'text_types': text_types
        }
    
    def _get_hierarchy(self, batches: List[Dict]) -> List[Dict[str, Any]]:
        """Extract document hierarchy"""
        hierarchy = []
        
        for batch in batches:
            doc = batch['doc']
            offset = batch.get('page_offset', 0)
            
            if not hasattr(doc, 'texts'):
                continue
            
            for item in doc.texts:
                label = getattr(item, 'label', None)
                
                if label and 'header' in label.lower():
                    text = getattr(item, 'text', '')
                    prov = getattr(item, 'prov', [])
                    
                    page_no = (prov[0].page_no + offset) if prov else None
                    
                    hierarchy.append({
                        'type': label,
                        'text': text,
                        'page': page_no,
                        'level': self._infer_heading_level(label)
                    })
        
        return sorted(hierarchy, key=lambda x: (x['page'] if x['page'] is not None else -1))
    
    def _infer_heading_level(self, label: str) -> int:
        """Infer heading level from label"""
        if 'title' in label.lower():
            return 1
        elif 'section' in label.lower():
            return 2
        elif 'subsection' in label.lower():
            return 3
        return 4
    
    def _get_tables(self, batches: List[Dict]) -> List[Dict[str, Any]]:
        """Extract table information"""
        tables_info = []
        global_table_counter = 1
        
        for batch in batches:
            doc = batch['doc']
            offset = batch.get('page_offset', 0)
            
            if not hasattr(doc, 'tables'):
                continue
            
            for table in doc.tables:
                try:
                    df = table.export_to_dataframe(doc=doc)
                    prov = getattr(table, 'prov', [])
                    
                    page_no = (prov[0].page_no + offset) if prov else None
                    
                    caption_text = getattr(table, 'caption_text', None)
                    caption = caption_text if caption_text and not callable(caption_text) else None
                    
                    # Convert DataFrame to list of lists for easier rendering
                    columns = list(df.columns)
                    rows = []
                    for _, row in df.iterrows():
                        rows.append([str(row[col]) for col in columns])
                    
                    tables_info.append({
                        'table_number': global_table_counter,
                        'page': page_no,
                        'caption': caption,
                        'columns': columns,
                        'rows': rows,
                        'shape': df.shape,
                        'is_empty': df.empty
                    })
                    global_table_counter += 1
                    
                except Exception as e:
                    print(f"Table processing error: {e}")
                    continue
        
        return tables_info
    
    def _get_pictures(self, batches: List[Dict]) -> List[Dict[str, Any]]:
        """Extract picture information"""
        pictures_info = []
        global_pic_counter = 1
        
        for batch in batches:
            doc = batch['doc']
            offset = batch.get('page_offset', 0)
            
            if not hasattr(doc, 'pictures'):
                continue
            
            for pic in doc.pictures:
                prov = getattr(pic, 'prov', [])
                
                if prov:
                    page_no = prov[0].page_no + offset
                    bbox = prov[0].bbox
                    
                    caption_text = getattr(pic, 'caption_text', None)
                    caption = caption_text if caption_text and not callable(caption_text) else None
                    
                    # Try to get image data (as base64 or path)
                    image_data = None
                    try:
                        if hasattr(pic, 'image') and pic.image is not None:
                            if hasattr(pic.image, 'pil_image'):
                                image_data = f"image_{global_pic_counter}"
                    except Exception as e:
                        print(f"Image extraction error: {e}")
                    
                    pictures_info.append({
                        'picture_number': global_pic_counter,
                        'page': page_no,
                        'caption': caption,
                        'has_image': image_data is not None,
                        'bounding_box': {
                            'left': bbox.l,
                            'top': bbox.t,
                            'right': bbox.r,
                            'bottom': bbox.b
                        } if bbox else None
                    })
                    global_pic_counter += 1
        
        return sorted(pictures_info, key=lambda x: (x['page'] if x['page'] is not None else -1))
