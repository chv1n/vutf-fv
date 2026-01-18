import fitz
import pymupdf.layout
import re
from typing import List, Optional
from models import Issue
from config import load_config
from utils import mm, to_mm, get_next_thai, parse_section_number, check_sequence_logic, parse_sub_section_bullet

def run_all_checks(pdf_path: str) -> List[Issue]:
    doc = fitz.open(pdf_path)
    issues = []
    
    CFG = load_config()
    
    # ดึงค่าให้ตรงกับ Key ใน config.json
    checks = CFG.get("check_list", {})
    rules = CFG.get("indent_rules", {})
    font_cfg = CFG.get("font", {})
    
    # ตั้งค่าตัวแปรสำหรับตรวจสอบ Margin และ Font
    m_top = mm(CFG["margin_mm"]["top"])
    m_bottom = mm(CFG["margin_mm"]["bottom"])
    m_left = mm(CFG["margin_mm"]["left"])
    
    font_keyword = font_cfg.get("name", "sarabun").lower()
    font_size_target = font_cfg.get("size", 16.0)
    font_tol = font_cfg.get("tolerance", 0.5)
    
    expected_page_str = None
    last_section_nums = None

    for i, page in enumerate(doc, 1):
        w, h = page.rect.width, page.rect.height
        
        # --- A. ตรวจลำดับเลขหน้า ---
        header_zone = fitz.Rect(w * 0.7, 0, w, m_top * 0.9)
        raw_header = page.get_text("text", clip=header_zone).strip()
        match_pg = re.search(r"(\d+|[ก-ฮ]+)", raw_header)
        current_page_label = match_pg.group(1) if match_pg else None

        if checks.get("check_page_seq") and current_page_label:
            if expected_page_str and current_page_label != expected_page_str:
                issues.append(Issue(i, "PAGE_SEQ_ERROR", f"ลำดับหน้าผิด: ควรเป็น {expected_page_str}", bbox=header_zone))
            
            if current_page_label.isdigit():
                expected_page_str = str(int(current_page_label) + 1)
            else:
                expected_page_str = get_next_thai(current_page_label)

        # --- B. ตรวจเนื้อหาภายในหน้า ---
        text_data = page.get_text("dict")
        for block in text_data["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    l_bbox = fitz.Rect(line["bbox"])
                    if l_bbox.y1 < m_top or l_bbox.y0 > (h - m_bottom): continue

                    spans = line["spans"]
                    line_text = "".join([s["text"] for s in spans]).strip()
                    if not line_text: continue
                    
                    # ระยะเยื้องจากขอบซ้ายที่วัดได้ (mm)
                    dist_mm = to_mm(l_bbox.x0 - m_left)

                    # 1. ตรวจ Margin
                    if checks.get("check_margin"):
                        if l_bbox.x0 < (m_left - 1.0):
                            issues.append(Issue(i, "MARGIN_LEFT", "ล้นขอบซ้าย", bbox=line["bbox"]))

                    # 2. ตรวจสอบระยะเยื้อง (Indentation) ตามหน้า 2.6.3 ในคู่มือ
                    if checks.get("check_indentation"):
                        # 2.1 หัวข้อย่อย (เช่น 1) )
                        digits = parse_sub_section_bullet(line_text)
                        if digits:
                            # หมายเลขต้องอยู่ที่ 15 mm
                            if abs(dist_mm - rules["sub_section_num"]) > rules["tolerance"]:
                                issues.append(Issue(i, "INDENT_ERR", f"เยื้องเลขหัวข้อผิด: {dist_mm:.1f}mm", bbox=line["bbox"]))
                            
                            # ชื่อหัวข้อเลข 1 หลัก (25mm) หรือ 2 หลัก (27.6mm)
                            if len(spans) > 1:
                                text_dist = to_mm(spans[1]["bbox"][0] - m_left)
                                target = rules["sub_section_text_1"] if digits == 1 else rules["sub_section_text_2"]
                                if abs(text_dist - target) > rules["tolerance"]:
                                    issues.append(Issue(i, "TEXT_ALIGN_ERR", "ชื่อหัวข้อย่อยเริ่มผิดตำแหน่ง", bbox=spans[1]["bbox"]))
                        
                        # 2.2 Bullet (•)
                        if "•" in line_text:
                            if abs(dist_mm - rules["bullet_point"]) > rules["tolerance"]:
                                issues.append(Issue(i, "BULLET_ERR", "จุด Bullet เยื้องผิด", bbox=line["bbox"]))

                    # 3. ตรวจ Font
                    if checks.get("check_font"):
                        for span in spans:
                            if not span["text"].strip(): continue
                            f_name = span["font"].lower()
                            if font_keyword not in f_name and "cidfont" not in f_name:
                                issues.append(Issue(i, "FONT_NAME", f"ฟอนต์ผิด: {span['font']}", bbox=span["bbox"]))
                            
                            if 10.0 <= span["size"] <= 20.0:
                                if abs(span["size"] - font_size_target) > font_tol:
                                    issues.append(Issue(i, "FONT_SIZE", f"ขนาดผิด: {span['size']:.1f}pt", bbox=span["bbox"]))

    return issues