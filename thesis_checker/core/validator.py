import fitz
import re
from typing import List

# Import models & config
from models import Issue
from config import load_config
from core.check_page_sequence import get_page_number_text
from utils import BLUE, mm, to_mm, get_next_thai

import utils as u

# Import Modular Checks
from core.check_margin import check_margin_rules
from core.check_font import check_font
from core.check_indent import check_indentation_rules
from core.check_paper_size import check_paper_size

from core.detect_chapter import detect_current_chapter

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RST = '\033[0m'

ENFORCE_A4_SIZE = False

def run_all_checks(pdf_path: str) -> List[Issue]:
    doc = fitz.open(pdf_path)
    issues = []
    
    # Pre-check: Paper Size (A4)
    # ถ้าขนาดกระดาษไม่ใช่ A4 ให้หยุดตรวจทันที
    paper_issues = check_paper_size(doc)
    if paper_issues and ENFORCE_A4_SIZE:
        print(f"{RED}Pre-check Failed: Found {len(paper_issues)} paper size errors{RST}")
        return paper_issues

    CFG = load_config()
    
    # Prepare Configurations
    checks = CFG.get("check_list", {})
    rules = CFG.get("indent_rules", {})
    
    font_cfg = CFG.get("font", {})
    margin_cfg = CFG.get("margin_mm", {})
    
    # Global Margins
    m_top = mm(margin_cfg.get("top", 25.4))
    m_bottom = mm(margin_cfg.get("bottom", 25.4))
    m_left = mm(margin_cfg.get("left", 38.1))
    
    expected_page_str = None

    print("=== Starting Full Validation (run_all_checks) ===")

    current_chapter = 0

    for i, page in enumerate(doc, 1):
        w, h = page.rect.width, page.rect.height

        #------------------get page number-----------------------------
        # เรียกฟังก์ชันดึงเลขหน้า
        page_num_str = get_page_number_text(page, m_top)
        
        # Print ออกมาดู (Debug)
        display_text = page_num_str if page_num_str else "-"
        print(f"Page {i}: Found Header = '{BLUE}{display_text}{RST}'")
        #--------------------------------------------------------------

        # อัปเดตว่าตอนนี้อยู่บทไหน
        current_chapter = detect_current_chapter(page, current_chapter)
        
        # Print เช็ค
        status_msg = f"Validating Page {i}"
        if current_chapter > 0:
            status_msg += f" (In Chapter {current_chapter})"
        else:
            status_msg += " (Pre-content / Abstract)"
            
        print(status_msg)
        
        # --- A. Page Sequence ---
        if checks.get("check_page_seq"):
            header_zone = fitz.Rect(w * 0.7, 0, w, m_top * 0.9)
            raw_header = page.get_text("text", clip=header_zone).strip()
            match_pg = re.search(r"(\d+|[ก-ฮ]+)", raw_header)
            current_page_label = match_pg.group(1) if match_pg else None

            if current_page_label:
                if expected_page_str and current_page_label != expected_page_str:
                    issues.append(Issue(i, "PAGE_SEQ_ERROR", "error", f"ลำดับหน้าผิด: ควรเป็น {expected_page_str}", bbox=header_zone))
                
                if current_page_label.isdigit():
                    expected_page_str = str(int(current_page_label) + 1)
                else:
                    expected_page_str = get_next_thai(current_page_label)

        # --- B. Prepare Lines ---
        text_data = page.get_text("dict")
        all_lines = []
        for block in text_data["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    all_lines.append(line)
        
        all_lines.sort(key=lambda l: l["bbox"][1])

        # --- C. Line Loop ---
        for line in all_lines:
            l_bbox = fitz.Rect(line["bbox"])
            
            # Filter Header/Footer
            if l_bbox.y1 < m_top or l_bbox.y0 > (h - m_bottom): continue

            spans = line["spans"]
            line_text = "".join([s["text"] for s in spans]).strip()
            if not line_text: continue
            
            dist_mm = to_mm(l_bbox.x0 - m_left)

            # 1. Margin
            if checks.get("check_margin"):
                margin_issues = check_margin_rules(
                    page_num=i, 
                    bbox=line["bbox"], 
                    margin_cfg=margin_cfg
                )
                issues.extend(margin_issues)

            # 2. Indentation
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

            # 3. Font
            if checks.get("check_font"):
                font_issues = check_font(
                    page_num=i, 
                    spans=spans, 
                    font_cfg=font_cfg
                )
                issues.extend(font_issues)

    return issues