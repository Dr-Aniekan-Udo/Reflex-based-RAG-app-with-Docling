"""
Document structure visualization for Docling processed documents.
Supports aggregated views from multiple batch-processed chunks.
"""
from typing import List, Dict, Any
# from docling_core.types.doc import DoclingDocument


class DocumentStructureVisualizer:
    """Extracts and organizes document structure from MULTIPLE Docling batches."""

    def __init__(self, docling_docs_list: List[Dict[str, Any]]):
        """
        Initialize with a LIST of Docling documents (batches).

        Args:
            docling_docs_list: List of dicts containing {'doc': DoclingDocument, 'page_offset': int}
        """
        # We store the list of batches, NOT a single doc
        self.docs_data = docling_docs_list

    def get_document_summary(self) -> Dict[str, Any]:
        """
        Get overall document summary statistics across all batches.

        Returns:
            Dictionary with aggregated document statistics
        """
        total_pages = 0
        total_texts = 0
        total_tables = 0
        total_pictures = 0
        text_types = {}
        
        # Loop through every batch to sum up the stats
        for batch in self.docs_data:
            doc = batch['doc']
            
            # Count pages (approximate based on batch size)
            pages = getattr(doc, 'pages', {})
            total_pages += len(pages) if pages else 0
            
            # Count elements
            texts = getattr(doc, 'texts', [])
            tables = getattr(doc, 'tables', [])
            pictures = getattr(doc, 'pictures', [])
            
            total_texts += len(texts)
            total_tables += len(tables)
            total_pictures += len(pictures)

            # Aggregate text types
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

    def get_document_hierarchy(self) -> List[Dict[str, Any]]:
        """
        Extract document hierarchy (headings and structure) from all batches.

        Returns:
            List of dictionaries containing hierarchical structure info
        """
        hierarchy = []

        for batch in self.docs_data:
            doc = batch['doc']
            # CRITICAL: Retrieve the offset we saved in document_processor.py
            offset = batch.get('page_offset', 0)

            if not hasattr(doc, 'texts'):
                continue

            for item in doc.texts:
                label = getattr(item, 'label', None)

                # Focus on headers and titles
                if label and 'header' in label.lower():
                    text = getattr(item, 'text', '')
                    prov = getattr(item, 'prov', [])
                    
                    # FIX: Add offset to page number
                    # prov[0].page_no is 1-based index inside the batch
                    page_no = (prov[0].page_no + offset) if prov else None

                    hierarchy.append({
                        'type': label,
                        'text': text,
                        'page': page_no,
                        'level': self._infer_heading_level(label)
                    })
        return hierarchy

    def _infer_heading_level(self, label: str) -> int:
        """Infer heading level from label."""
        if 'title' in label.lower():
            return 1
        elif 'section' in label.lower():
            return 2
        elif 'subsection' in label.lower():
            return 3
        else:
            return 4

    def get_tables_info(self) -> List[Dict[str, Any]]:
        """
        Extract table information from all batches and convert to DataFrames.

        Returns:
            List of dictionaries with table metadata and DataFrame
        """
        tables_info = []
        global_table_counter = 1  # Keep a running count across batches

        for batch in self.docs_data:
            doc = batch['doc']
            offset = batch.get('page_offset', 0)

            if not hasattr(doc, 'tables'):
                continue

            for table in doc.tables:
                try:
                    df = table.export_to_dataframe(doc=doc)
                    prov = getattr(table, 'prov', [])
                    
                    # FIX: Add offset to page number
                    page_no = (prov[0].page_no + offset) if prov else None
                    
                    caption_text = getattr(table, 'caption_text', None)
                    caption = caption_text if caption_text and not callable(caption_text) else None

                    tables_info.append({
                        'table_number': global_table_counter,
                        'page': page_no,
                        'caption': caption,
                        'dataframe': df,
                        'shape': df.shape,
                        'is_empty': df.empty
                    })
                    global_table_counter += 1

                except Exception as e:
                    # Handle tables that can't be converted
                    print(f"Warning: Could not process table: {e}")
                    continue

        return tables_info

    def get_pictures_info(self) -> List[Dict[str, Any]]:
        """
        Extract picture/image metadata and image data from all batches.

        Returns:
            List of dictionaries with picture information and PIL images
        """
        pictures_info = []
        global_pic_counter = 1

        for batch in self.docs_data:
            doc = batch['doc']
            offset = batch.get('page_offset', 0)

            if not hasattr(doc, 'pictures'):
                continue

            for pic in doc.pictures:
                prov = getattr(pic, 'prov', [])
                
                if prov:
                    # FIX: Add offset to page number
                    page_no = prov[0].page_no + offset
                    bbox = prov[0].bbox

                    # Get caption if available
                    caption_text = getattr(pic, 'caption_text', None)
                    caption = caption_text if caption_text and not callable(caption_text) else None

                    # Get PIL image if available
                    pil_image = None
                    try:
                        if hasattr(pic, 'image') and pic.image is not None:
                            if hasattr(pic.image, 'pil_image'):
                                pil_image = pic.image.pil_image
                    except Exception as e:
                        print(f"Warning: Could not extract image: {e}")

                    pictures_info.append({
                        'picture_number': global_pic_counter,
                        'page': page_no,
                        'caption': caption,
                        'pil_image': pil_image, 
                        'bounding_box': {
                            'left': bbox.l,
                            'top': bbox.t,
                            'right': bbox.r,
                            'bottom': bbox.b
                        } if bbox else None
                    })
                    global_pic_counter += 1

        return pictures_info

    def export_full_structure(self) -> Dict[str, Any]:
        """
        Export complete document structure.

        Returns:
            Dictionary containing all structure information
        """
        return {
            'summary': self.get_document_summary(),
            'hierarchy': self.get_document_hierarchy(),
            'tables': self.get_tables_info(),
            'pictures': self.get_pictures_info()
        }
