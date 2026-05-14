"""
Document structure visualization for Docling processed documents.
Pre-serializes everything into plain Python dicts/lists so Reflex state stays safe.
"""
import base64
from io import BytesIO
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
                    weight = "bold" if level <= 2 else "medium"
                    color = "blue" if level == 1 else "black"
                    hierarchy.append({
                        'type': label,
                        'text': ("  " * (level - 1)) + text,
                        'page': page_no,
                        'level': level,
                        'weight': weight,
                        'color': color,
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

                    # Build structured rows/columns for frontend table rendering
                    columns = []
                    rows = []
                    if not df.empty:
                        columns = [str(c) for c in df.columns]
                        for _, row in df.iterrows():
                            row_list = []
                            for c in df.columns:
                                val = str(row[c]) if row[c] is not None else ""
                                if val == "nan":
                                    val = ""
                                row_list.append(val)
                            rows.append(row_list)

                    page_str = f"Page {page_no}" if page_no is not None else ""
                    tables_info.append({
                        'table_number': global_table_counter,
                        'page': page_no,
                        'page_str': page_str,
                        'caption': caption,
                        'display_title': f"Table {global_table_counter} ({page_str})",
                        'columns': columns,
                        'rows': rows,
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

                    image_data = None
                    has_image = False
                    try:
                        if hasattr(pic, 'image') and pic.image is not None:
                            if hasattr(pic.image, 'pil_image') and pic.image.pil_image is not None:
                                has_image = True
                                buffer = BytesIO()
                                pic.image.pil_image.save(buffer, format="PNG")
                                img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                                image_data = f"data:image/png;base64,{img_base64}"
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
                        'image_data': image_data,
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
