import fitz
from typing import List
from models import Issue
from config import DEFAULT_CONFIG, DEBUG
from utils import mm, to_mm
from tqdm import tqdm

def annotate_and_save_pdf(input_path: str, output_path: str, issues: List[Issue]):
    print(f"Opening PDF: {input_path}")
    doc = fitz.open(input_path)
    
    CFG = DEFAULT_CONFIG
    m_top = mm(CFG.get("margin_mm", {}).get("top", 25.4))
    m_bottom = mm(CFG.get("margin_mm", {}).get("bottom", 25.4))
    m_left = mm(CFG.get("margin_mm", {}).get("left", 38.1))
    m_right = mm(CFG.get("margin_mm", {}).get("right", 25.4))

    for i, page in enumerate(tqdm(doc, desc="Annotating PDF", unit="page"), 1):
        w, h = page.rect.width, page.rect.height
        
        # 1. Draw Margins (Green Dashed)
        # -------------------------------------------------------
        r_margin = fitz.Rect(m_left, m_top, w - m_right, h - m_bottom)
        annot = page.add_rect_annot(r_margin)
        annot.set_border(width=0.5)
        annot.set_colors(stroke=(0, 1, 0))
        annot.update()

        # 2. Collect Data & Draw Text Boxes
        # -------------------------------------------------------
        text_data = page.get_text("dict")
        all_text_lines = []
        raw_lines = []

        for block in text_data["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    line_bbox = fitz.Rect(line["bbox"])
                    
                    # ข้าม Header/Footer
                    if line_bbox.y1 < m_top or line_bbox.y0 > (h - m_bottom): continue
                    
                    text_content = "".join([s["text"] for s in line["spans"]]).strip()
                    if not text_content: continue
                    
                    # เก็บข้อมูลไว้คำนวณ Spacing
                    all_text_lines.append(line_bbox)

                    # -------------------------------------------------------
                    # [A] Draw Text Boxes (Blue)
                    # -------------------------------------------------------
                    annot = page.add_rect_annot(line_bbox)
                    annot.set_border(width=0.3)    
                    annot.set_colors(stroke=(0, 0, 1)) # สีน้ำเงิน
                    annot.update()
                    # -------------------------------------------------------

                    # เก็บข้อมูล Indentation
                    valid_x0s = [s["bbox"][0] for s in line["spans"] if s["text"].strip()]
                    if valid_x0s:
                        raw_lines.append({
                            "y0": line_bbox.y0, 
                            "x0": min(valid_x0s), 
                            "mid_y": (line_bbox.y0 + line_bbox.y1) / 2
                        })

        # [B] Indentation Lines (Cyan)
        # -------------------------------------------------------
        if raw_lines:
            raw_lines.sort(key=lambda x: x["y0"])
            merged_lines = []
            curr = raw_lines[0]
            for l in raw_lines[1:]:
                if abs(l["y0"] - curr["y0"]) < 3:
                    curr["x0"] = min(curr["x0"], l["x0"])
                else: 
                    merged_lines.append(curr); curr = l
            merged_lines.append(curr)

            for line in merged_lines:
                p1 = (m_left, line["mid_y"])
                p2 = (line["x0"], line["mid_y"])
                annot = page.add_line_annot(p1, p2)
                annot.set_border(width=0.5)
                annot.set_colors(stroke=(0, 0.8, 0.8))
                annot.update()

        # [C] Tables & Images
        # -------------------------------------------------------
        visual_objects = []
        # try:
        #     for tab in page.find_tables():
        #         r = fitz.Rect(tab.bbox); visual_objects.append(r)
        #         annot = page.add_rect_annot(r)
        #         annot.set_border(width=1.5)
        #         annot.set_colors(stroke=(1, 0.5, 0))
        #         annot.set_info(content="Table")
        #         annot.update()
        # except: pass

        try:
            for img in page.get_images():
                for r in page.get_image_rects(img):
                    if r.width > 30 and r.height > 30 and not any(t.contains(r) for t in visual_objects):
                        visual_objects.append(r)
                        annot = page.add_rect_annot(r)
                        annot.set_border(width=1.5)
                        annot.set_colors(stroke=(1, 0.5, 0))
                        annot.update()
        except: pass

        # [E] Issues (Red Box + Text)
        # -------------------------------------------------------
        page_issues = [x for x in issues if x.page == i]
        for issue in page_issues:
            color = (1, 0, 0) if issue.severity == "error" else (1, 0.6, 0)
            if issue.bbox:
                r = fitz.Rect(issue.bbox)
                
                # 1. กรอบแดง
                annot = page.add_rect_annot(r)
                annot.set_border(width=2.0)
                annot.set_colors(stroke=color)
                annot.update()
                
                # 2. ข้อความ Error Code
                text_annot = page.add_freetext_annot(
                    fitz.Rect(r.x0, r.y0 - 15, r.x0 + 200, r.y0), 
                    issue.code, 
                    fontsize=8, 
                    fontname="helv", 
                    text_color=color
                )
                text_annot.update()

    # Save
    print(f"Saving annotated PDF to: {output_path}")
    doc.save(output_path, garbage=4, deflate=True) 
    doc.close()