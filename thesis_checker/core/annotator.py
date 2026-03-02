import fitz
from typing import List
from models import Issue
from config import DEFAULT_CONFIG
from utils import mm
from tqdm import tqdm


DEBUG = False 

def annotate_and_save_pdf(input_path: str, output_path: str, issues: List[Issue]):
    print(f"[Annotator] Opening PDF: {input_path}")
    doc = fitz.open(input_path)
    
    CFG = DEFAULT_CONFIG
    m_top = mm(CFG.get("margin_mm", {}).get("top", 25.4))
    m_bottom = mm(CFG.get("margin_mm", {}).get("bottom", 25.4))
    m_left = mm(CFG.get("margin_mm", {}).get("left", 38.1))
    m_right = mm(CFG.get("margin_mm", {}).get("right", 25.4))

    for i, page in enumerate(tqdm(doc, desc="Annotating PDF", unit="page"), 1):
        w, h = page.rect.width, page.rect.height

        # วาดเส้น Margin 
        r_margin = fitz.Rect(m_left, m_top, w - m_right, h - m_bottom)
        annot = page.add_rect_annot(r_margin)
        annot.set_border(width=0.5, dashes=[2])
        annot.set_colors(stroke=(0, 1, 0))
        annot.update()

        if DEBUG:

            # วาดกรอบตารางและรูปภาพ
            visual_objects = []
            try:
                # รูปภาพ
                for img in page.get_images():
                    for r in page.get_image_rects(img):
                        if r.width > 30 and r.height > 30: # กรองรูปเล็กๆ ออก
                            visual_objects.append(r)
                            annot = page.add_rect_annot(r)
                            annot.set_border(width=1.0, dashes=[1, 2])
                            annot.set_colors(stroke=(1, 0.5, 0)) # สีส้ม
                            annot.set_info(content="Image/Visual Area (Skipped)", title="Debug")
                            annot.update()
                # ตาราง
                for tab in page.find_tables():
                    r = fitz.Rect(tab.bbox)
                    visual_objects.append(r)
                    annot = page.add_rect_annot(r)
                    annot.set_border(width=1.0, dashes=[1, 2])
                    annot.set_colors(stroke=(1, 0.5, 0))
                    annot.set_info(content="Table Area (Skipped)", title="Debug")
                    annot.update()
            except: pass
    
            # วาด Text Box และเส้น Indent
            text_data = page.get_text("dict")
            raw_lines = []

            for block in text_data["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        line_bbox = fitz.Rect(line["bbox"])
                        # ข้าม Header/Footer ในการวาด Debug
                        if line_bbox.y1 < m_top or line_bbox.y0 > (h - m_bottom): continue
                        
                        text_content = "".join([s["text"] for s in line["spans"]]).strip()
                        if not text_content: continue
                        
                        # วาดกรอบข้อความ
                        annot = page.add_rect_annot(line_bbox)
                        annot.set_border(width=0.3)    
                        annot.set_colors(stroke=(0, 0, 1))
                        annot.update()

                        # เก็บข้อมูลเพื่อวาดเส้น Indent
                        valid_x0s = [s["bbox"][0] for s in line["spans"] if s["text"].strip()]
                        if valid_x0s:
                            raw_lines.append({
                                "y0": line_bbox.y0, 
                                "x0": min(valid_x0s), 
                                "mid_y": (line_bbox.y0 + line_bbox.y1) / 2
                            })

        page_issues = [x for x in issues if x.page == i]
        
        for issue in page_issues:
            color = (1, 0, 0) if issue.severity == "error" else (1, 0.6, 0)
            
            if issue.bbox:
                r = fitz.Rect(issue.bbox)
                
                # เช็ค BBox ผิดปกติ
                if r.is_empty or r.is_infinite or r.width <= 0 or r.height <= 0:
                    continue
                
                # วาดกรอบสี่เหลี่ยม (Frame)
                annot = page.add_rect_annot(r)
                annot.set_border(width=0.5)
                annot.set_colors(stroke=color)
                
                annot.set_info(content=issue.message, title="Thesis Checker", subject=issue.code) 
                annot.update()

                # คำนวณตำแหน่งเขียนข้อความ (มุมซ้ายบน)
                text_point = fitz.Point(r.x0, r.y0 - 2)
                
                # ถ้ากรอบชิดขอบบนเกินไป ให้ย้ายลงมาข้างล่าง
                if r.y0 < 15:
                    text_point = fitz.Point(r.x0, r.y1 + 8)

                # เขียนข้อความฝังลงใน PDF
                page.insert_text(
                    text_point,
                    str(issue.code), 
                    fontsize=6,       
                    fontname="helv", 
                    color=color       
                )

    # Save PDF
    print(f"[Annotator] Saving annotated PDF to: {output_path}")
    doc.save(output_path, garbage=4, deflate=True) 
    doc.close()