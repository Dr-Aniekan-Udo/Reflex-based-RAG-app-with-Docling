"""
Document structure visualization for Docling processed documents.
Pre-serializes everything into plain Python dicts/lists so Reflex state stays safe.
"""
from typing import List, Dict, Any, Optional


class DocumentStructureVisualizer:
    """Extracts and organizes document structure from MULTIPLE Docling batches."""

    def __init__(self, docling_docs_list: List[Dict[str, Any]]):
        self.docs_data = docling_docs_list

    def get_document_summary(self) -> Dict[str, Any]:
        total_pages = 0
        total_texts = 0
        total_tables = 0
        total_pictures = 0
        text_types = {}

        for batch in self.docs_data:
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

    def get_document_hierarchy(self) -> List[Dict[str, Any]]:
        hierarchy = []
        for batch in self.docs_data:
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
                    level = self._infer_heading_level(label)
                    hierarchy.append({
                        'type': label,
                        'text': ("  " * (level - 1)) + text,
                        'page': page_no,
                        'level': level,
                        'page_str': f"Page {page_no}" if page_no is not None else "Unknown Page"
                    })
        return sorted(hierarchy, key=lambda x: (x['page'] if x['page'] is not None else -1))

    def _infer_heading_level(self, label: str) -> int:
        if 'title' in label.lower():
            return 1
        elif 'section' in label.lower():
            return 2
        elif 'subsection' in label.lower():
            return 3
        return 4

    def get_tables_info(self) -> List[Dict[str, Any]]:
        tables_info = []
        global_table_counter = 1
        for batch in self.docs_data:
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

                    markdown_lines = []
                    if caption:
                        markdown_lines.append(f"**{caption}**")
                    if not df.empty:
                        try:
                            markdown_lines.append(df.to_markdown(index=False))
                        except Exception:
                            markdown_lines.append(str(df))
                    table_markdown = "\n\n".join(markdown_lines)

                    page_str = f"Page {page_no}" if page_no is not None else ""
                    tables_info.append({
                        'table_number': global_table_counter,
                        'page': page_no,
                        'page_str': page_str,
                        'caption': caption,
                        'display_title': f"Table {global_table_counter} ({page_str})",
                        'markdown': table_markdown,
                        'shape': str(df.shape),
                        'is_empty': df.empty
                    })
                    global_table_counter += 1
                except Exception as e:
                    print(f"Warning: Could not process table: {e}")
                    continue
        return tables_info

    def get_pictures_info(self) -> List[Dict[str, Any]]:
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
                    page_no = prov[0].page_no + offset
                    bbox = prov[0].bbox

                    caption_text = getattr(pic, 'caption_text', None)
                    caption = caption_text if caption_text and not callable(caption_text) else None

                    has_image = False
                    try:
                        if hasattr(pic, 'image') and pic.image is not None:
                            if hasattr(pic.image, 'pil_image'):
                                has_image = True
                    except Exception as e:
                        print(f"Warning: Could not extract image: {e}")

                    page_str = f"Page {page_no}" if page_no is not None else ""
                    bbox_text = None
                    if bbox:
                        bbox_text = f"BBox: ({bbox.l:.1f}, {bbox.t:.1f}) - ({bbox.r:.1f}, {bbox.b:.1f})"
                    pictures_info.append({
                        'picture_number': global_pic_counter,
                        'page': page_no,
                        'page_str': page_str,
                        'caption': caption,
                        'has_image': has_image,
                        'display_title': f"Image {global_pic_counter} ({page_str})",
                        'bounding_box': {
                            'left': bbox.l,
                            'top': bbox.t,
                            'right': bbox.r,
                            'bottom': bbox.b
                        } if bbox else None,
                        'bbox_text': bbox_text
                    })
                    global_pic_counter += 1
        return sorted(pictures_info, key=lambda x: (x['page'] if x['page'] is not None else -1))

    def export_full_structure(self) -> Dict[str, Any]:
        return {
            'summary': self.get_document_summary(),
            'hierarchy': self.get_document_hierarchy(),
            'tables': self.get_tables_info(),
            'pictures': self.get_pictures_info()
        }
