import fitz
import pymupdf.layout
import re
from typing import List
from models import Issue
from config import load_config
from core.check_font import check_font
from core.check_indent import check_indentation_rules
from core.check_section_sequence import check_section_rules
from utils import mm, to_mm, parse_section_number, check_sequence_logic, parse_sub_section_bullet

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RST = '\033[0m'

def check_chapter_1(pdf_path: str) -> List[Issue]:
    doc = fitz.open(pdf_path)
    issues = []
    CFG = load_config()
    
    # Config
    checks = CFG.get("check_list", {})
    
    rules = CFG.get("indent_rules", {})
    font_cfg = CFG.get("font", {})
    m_top, m_bottom = mm(CFG["margin_mm"]["top"]), mm(CFG["margin_mm"]["bottom"])
    m_left = mm(CFG["margin_mm"]["left"])
    font_keyword = font_cfg.get("name", "sarabun").lower()
    font_size_target, font_tol = font_cfg.get("size", 16.0), font_cfg.get("tolerance", 0.5)
    
    last_section_nums = None # ตัวแปรจำเลขหัวข้อล่าสุด (สำคัญมาก)

    print("=== Starting Validation (Sorted Lines) ===")

    for i, page in enumerate(doc, 1):
        # 1. รวบรวมบรรทัดทั้งหมดในหน้าก่อน
        text_data = page.get_text("dict")
        all_lines = []
        for block in text_data["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    all_lines.append(line)
        
        # 2. เรียงลำดับจาก "บนลงล่าง" (สำคัญที่สุดสำหรับการเช็ค Sequence)
        all_lines.sort(key=lambda l: l["bbox"][1])

        print(f"  Validating Page {i}...")
        
        # 3. วนลูปตรวจทีละบรรทัดที่เรียงแล้ว
        for line in all_lines:
            l_bbox = fitz.Rect(line["bbox"])
            
            # กรอง Margin (ข้าม Header/Footer)
            if l_bbox.y1 < m_top or l_bbox.y0 > (page.rect.height - m_bottom): continue

            spans = line["spans"]
            line_text = "".join([s["text"] for s in spans]).strip()
            if not line_text: continue
            
            dist_mm = to_mm(l_bbox.x0 - m_left)

            # [Check 1] Section Sequence
            if checks.get("check_section_seq"):
                seq_issues, last_section_nums = check_section_rules(
                    page_num=i,
                    line_text=line_text,
                    bbox=line["bbox"],
                    chapter_num=1,       # ส่งเลข 1 เพราะนี่คือ check_chapter_1
                    last_section_nums=last_section_nums
                )
                issues.extend(seq_issues)

            # [Check 2] Indentation
            if checks.get("check_indentation"):
                indent_issues = check_indentation_rules(
                page_num=i,
                line_text=line_text,
                spans=spans,
                bbox=line["bbox"],
                dist_mm=dist_mm,
                rules=rules,
                m_left=m_left
            )
                issues.extend(indent_issues) # เพิ่ม issue ที่เจอเข้า list หลัก

            # [Check 3] Font
            if checks.get("check_font"):
                font_issues = check_font(
                page_num=i,
                spans=spans,
                font_cfg=font_cfg  # ส่ง dict ของ config font ไปก้อนเดียวเลย
            )
                issues.extend(font_issues)

    return issues