import fitz
from typing import List
from models import Issue
from config import load_config
from core.check_font import check_font
from core.check_indent import check_indentation_rules
from core.check_section_sequence import check_section_rules
from core.check_margin import check_margin_rules
from utils import mm, to_mm

def validate_chapter(pdf_path: str, chapter_num: int) -> List[Issue]:
    doc = fitz.open(pdf_path)
    issues = []
    CFG = load_config()
    
    # Load Config
    checks = CFG.get("check_list", {})
    rules = CFG.get("indent_rules", {})
    font_cfg = CFG.get("font", {})
    
    m_top, m_bottom = mm(CFG["margin_mm"]["top"]), mm(CFG["margin_mm"]["bottom"])
    m_left = mm(CFG["margin_mm"]["left"])
    
    # ตัวแปรจำเลขหัวข้อล่าสุด
    last_section_nums = None 

    print(f"=== Starting Validation for Chapter {chapter_num} ===")

    for i, page in enumerate(doc, 1):
        # 1. รวบรวมบรรทัด
        text_data = page.get_text("dict")
        all_lines = []
        for block in text_data["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    all_lines.append(line)
        
        # 2. เรียงลำดับบรรทัด
        all_lines.sort(key=lambda l: l["bbox"][1])

        print(f"  Validating Page {i}...")
        
        for line in all_lines:
            l_bbox = fitz.Rect(line["bbox"])
            
            # กรอง Margin
            if l_bbox.y1 < m_top or l_bbox.y0 > (page.rect.height - m_bottom): continue

            spans = line["spans"]
            line_text = "".join([s["text"] for s in spans]).strip()
            if not line_text: continue
            
            dist_mm = to_mm(l_bbox.x0 - m_left)

            # ตรวจ Margin
            if checks.get("check_margin"):
                margin_issues = check_margin_rules(
                        page_num=i, 
                        bbox=line["bbox"], 
                        margin_cfg=margin_cfg
                )
                issues.extend(margin_issues)


            # [Check 1] Section Sequence
            # ส่ง chapter_num ที่รับเข้ามา เข้าไปในฟังก์ชันตรวจสอบ
            if checks.get("check_section_seq"):
                seq_issues, last_section_nums = check_section_rules(
                    page_num=i,
                    line_text=line_text,
                    bbox=line["bbox"],
                    chapter_num=chapter_num,  # <--- จุดที่ทำให้ Dynamic
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
                issues.extend(indent_issues)

            # [Check 3] Font
            if checks.get("check_font"):
                font_issues = check_font(
                    page_num=i,
                    spans=spans,
                    font_cfg=font_cfg
                )
                issues.extend(font_issues)

    return issues