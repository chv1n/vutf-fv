import fitz
from typing import List
from models import Issue
from config import DEFAULT_CONFIG, DEBUG
from utils import mm, to_mm
from tqdm import tqdm

DEBUG = True

def annotate_and_save_pdf(input_path: str, output_path: str, issues: List[Issue]):
    print(f"Opening PDF: {input_path}")
    doc = fitz.open(input_path)
    out = fitz.open()
    
    CFG = DEFAULT_CONFIG
    m_top = mm(CFG.get("margin_mm", {}).get("top", 25.4))
    m_bottom = mm(CFG.get("margin_mm", {}).get("bottom", 25.4))
    m_left = mm(CFG.get("margin_mm", {}).get("left", 38.1))
    m_right = mm(CFG.get("margin_mm", {}).get("right", 25.4))

    # ใช้ tqdm เพื่อแสดง Progress Bar
    for i, page in enumerate(tqdm(doc, desc="Annotating PDF", unit="page"), 1):
        # สร้างหน้าใหม่ในไฟล์ Output ให้ขนาดเท่าหน้าเดิม
        w, h = page.rect.width, page.rect.height
        np = out.new_page(-1, width=w, height=h)
        np.show_pdf_page(np.rect, doc, i-1)

        # -------------------------------------------------------
        # 1. Draw Margins (Green Dashed Line)
        # -------------------------------------------------------
        np.draw_rect(
            fitz.Rect(m_left, m_top, w - m_right, h - m_bottom), 
            color=(0, 1, 0), width=0.5, dashes=[2, 2]
        )

        # -------------------------------------------------------
        # 2. Collect Data (Text Lines & Blocks) - Loop เดียวจบ
        # -------------------------------------------------------
        text_data = page.get_text("dict")
        all_text_lines = []  # เก็บ bbox ของบรรทัดทั้งหมด (เอาไว้เช็ค Spacing)
        raw_lines = []       # เก็บพิกัด x0 ของบรรทัด (เอาไว้เช็ค Indent)

        for block in text_data["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    line_bbox = fitz.Rect(line["bbox"])
                    
                    # ข้าม Header/Footer (อยู่นอก Margin บนล่าง)
                    if line_bbox.y1 < m_top or line_bbox.y0 > (h - m_bottom): 
                        continue

                    # หาข้อความจริงๆ (ไม่เอาช่องว่าง)
                    text_content = "".join([s["text"] for s in line["spans"]]).strip()
                    if not text_content: 
                        continue

                    # [A] Draw Text Boxes (Blue - Debug Only)
                    # np.draw_rect(line_bbox, color=(0, 0, 1), width=0.3) # เปิดถ้าอยากเห็นกรอบข้อความทุกบรรทัด
                    all_text_lines.append(line_bbox)

                    # เก็บข้อมูล Indentation
                    valid_x0s = [s["bbox"][0] for s in line["spans"] if s["text"].strip()]
                    if valid_x0s:
                        raw_lines.append({
                            "y0": line_bbox.y0, 
                            "x0": min(valid_x0s), 
                            "mid_y": (line_bbox.y0 + line_bbox.y1) / 2
                        })

        # -------------------------------------------------------
        # [B] Draw Indentation Lines (Cyan)
        # -------------------------------------------------------
        # (ย้ายออกมานอก Loop Block แล้ว)
        if raw_lines:
            raw_lines.sort(key=lambda x: x["y0"])
            merged_lines = []
            curr = raw_lines[0]
            
            # Logic รวมบรรทัดที่อยู่ระดับเดียวกัน (บรรทัดเดียวกันแต่คนละ Span)
            for l in raw_lines[1:]:
                if abs(l["y0"] - curr["y0"]) < 3: # ถ้าความสูงใกล้กันมาก ถือเป็นบรรทัดเดิม
                    curr["x0"] = min(curr["x0"], l["x0"])
                else: 
                    merged_lines.append(curr)
                    curr = l
            merged_lines.append(curr)

            # วาดเส้น Indent จากขอบซ้ายมาถึงตัวหนังสือ
            for line in merged_lines:
                # วาดเส้นสีฟ้าจางๆ
                np.draw_line((m_left, line["mid_y"]), (line["x0"], line["mid_y"]), color=(0, 0.8, 0.8), width=0.5)

        # -------------------------------------------------------
        # [C] Detect Tables & Images
        # -------------------------------------------------------
        visual_objects = []
        
        # Tables
        try:
            for tab in page.find_tables():
                r = fitz.Rect(tab.bbox)
                visual_objects.append(r)
                np.draw_rect(r, color=(0.5, 0, 0.5), width=2.0)
                np.insert_textbox(r, "Table", fontsize=7, color=(0.5, 0, 0.5), align=1)
        except Exception: 
            pass

        # Images
        try:
            for img in page.get_images():
                # Loop หาตำแหน่งรูปภาพบนหน้า
                for r in page.get_image_rects(img):
                    # กรองรูปเล็กๆ หรือรูปที่ซ้อนทับกับตารางออก
                    if r.width > 30 and r.height > 30 and not any(t.contains(r) for t in visual_objects):
                        visual_objects.append(r)
                        np.draw_rect(r, color=(1, 0.5, 0), width=1.5)
                        np.insert_textbox(r, "Image", fontsize=7, color=(1, 0.5, 0), align=1)
        except Exception: 
            pass

        # -------------------------------------------------------
        # [D] Spacing Calculation (Magenta)
        # -------------------------------------------------------
        for obj in visual_objects:
            # หาบรรทัดข้อความที่อยู่ "เหนือ" วัตถุนี้ที่ใกล้ที่สุด
            candidates_above = [l for l in all_text_lines if l.y1 < obj.y0 and l.y0 > (m_top * 0.8)]
            
            if candidates_above:
                nearest = max(candidates_above, key=lambda l: l.y1)
                dist = obj.y0 - nearest.y1
                
                # ถ้าระยะห่างน้อยกว่า 100mm (กันเพี้ยน) ให้วาดเส้นบอกระยะ
                if dist < mm(100):
                    line_x = obj.x0 + 10
                    np.draw_line((line_x, nearest.y1), (line_x, obj.y0), color=(0.8, 0, 0.5), width=0.8)
                    np.insert_text((line_x + 2, obj.y0 - 2), f"{to_mm(dist):.1f}mm", fontsize=6, color=(0.8, 0, 0.5))

        # -------------------------------------------------------
        # [E] Draw Identified Issues (Red Box) -> วาดท้ายสุดจะได้อยู่บนสุด
        # -------------------------------------------------------
        page_issues = [x for x in issues if x.page == i]
        for issue in page_issues:
            color = (1, 0, 0) if issue.severity == "error" else (1, 0.6, 0) # แดง หรือ ส้ม
            
            if issue.bbox:
                r = fitz.Rect(issue.bbox)
                # วาดกรอบ Error
                np.draw_rect(r, color=color, width=2)
                # แปะชื่อ Error Code ไว้บนกรอบ
                np.insert_text((r.x0, r.y0 - 2), f"{issue.code}", fontsize=8, color=color)

    # Save ไฟล์
    print(f"Saving annotated PDF to: {output_path}")
    out.save(output_path)
    out.close()
    doc.close()