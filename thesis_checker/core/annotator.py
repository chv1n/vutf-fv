import fitz
from typing import List
from models import Issue
from config import DEFAULT_CONFIG, DEBUG
from utils import mm, to_mm

DEBUG = True

def annotate_and_save_pdf(input_path: str, output_path: str, issues: List[Issue]):
    doc = fitz.open(input_path)
    out = fitz.open()
    CFG = DEFAULT_CONFIG
    m_top, m_bottom = mm(CFG["margin_mm"]["top"]), mm(CFG["margin_mm"]["bottom"])
    m_left, m_right = mm(CFG["margin_mm"]["left"]), mm(CFG["margin_mm"]["right"])

    for i, page in enumerate(doc, 1):
        np = out.new_page(-1, width=page.rect.width, height=page.rect.height)
        np.show_pdf_page(np.rect, doc, i-1)
        w, h = page.rect.width, page.rect.height
        
        # 1. Margin (Green)
        np.draw_rect(fitz.Rect(m_left, m_top, w - m_right, h - m_bottom), color=(0, 1, 0), width=0.5, dashes=[2, 2])

        print(f"Annotating Page {i}...")
        text_data = page.get_text("dict")
        all_text_lines = []
            
        # [A] Text Boxes (Blue)
        for block in text_data["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    if "".join([s["text"] for s in line["spans"]]).strip():
                        r = fitz.Rect(line["bbox"])
                        np.draw_rect(r, color=(0, 0, 1), width=0.3)
                        all_text_lines.append(r)

        # [B] Indentation (Cyan)
        raw_lines = []
        for block in text_data["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    line_bbox = fitz.Rect(line["bbox"])
                    if line_bbox.y1 < m_top or line_bbox.y0 > (h - m_bottom): continue
                    valid_x0s = [s["bbox"][0] for s in line["spans"] if s["text"].strip()]
                    if not valid_x0s: continue
                    raw_lines.append({"y0": line_bbox.y0, "x0": min(valid_x0s), "mid_y": (line_bbox.y0 + line_bbox.y1) / 2})

            raw_lines.sort(key=lambda x: x["y0"])
            merged_lines = []
            if raw_lines:
                curr = raw_lines[0]
                for l in raw_lines[1:]:
                    if abs(l["y0"] - curr["y0"]) < 3: curr["x0"] = min(curr["x0"], l["x0"])
                    else: merged_lines.append(curr); curr = l
                merged_lines.append(curr)

            for line in merged_lines:
                dist_mm = to_mm(line["x0"] - m_left)
                np.draw_line((m_left, line["mid_y"]), (line["x0"], line["mid_y"]), color=(0, 0.8, 0.8), width=0.5)

            # [C] Tables & Images
            visual_objects = []
            try:
                for tab in page.find_tables():
                    r = fitz.Rect(tab.bbox); visual_objects.append(r)
                    np.draw_rect(r, color=(0.5, 0, 0.5), width=2.0)
                    np.insert_textbox(r, "Table", fontsize=7, color=(0.5, 0, 0.5), align=1)
            except: pass

            for img in page.get_images():
                try:
                    for r in page.get_image_rects(img):
                        if r.width > 30 and r.height > 30 and not any(t.contains(r) for t in visual_objects):
                            visual_objects.append(r)
                            np.draw_rect(r, color=(1, 0.5, 0), width=1.5)
                            np.insert_textbox(r, "Image", fontsize=7, color=(1, 0.5, 0), align=1)
                except: pass

            # [D] Spacing Calculation (Magenta)
            for obj in visual_objects:
                candidates_above = [l for l in all_text_lines if l.y1 < obj.y0 and l.y0 > (m_top * 0.8)]
                if candidates_above:
                    nearest = max(candidates_above, key=lambda l: l.y1)
                    dist = obj.y0 - nearest.y1
                    if dist < mm(100):
                        np.draw_line((obj.x0+10, nearest.y1), (obj.x0+10, obj.y0), color=(0.8, 0, 0.5), width=0.8)
                        np.insert_text((obj.x0+12, obj.y0-2), f"{to_mm(dist):.1f}mm", fontsize=6, color=(0.8, 0, 0.5))

        # Draw Issues
        for issue in [x for x in issues if x.page == i]:
            color = (1, 0, 0) if issue.severity == "error" else (1, 0.5, 0)
            if issue.bbox:
                r = fitz.Rect(issue.bbox)
                np.draw_rect(r, color=color, width=1.5)
                np.insert_text((r.x0, r.y0 - 2), f"{issue.code}", fontsize=6, color=color)

    out.save(output_path); out.close()