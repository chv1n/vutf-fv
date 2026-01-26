import fitz
import re
from typing import List

# Import models & config
from models import Issue
from config import load_config
from core.check_page_sequence import get_page_number_text, get_next_page_label
from utils import BLUE, mm, to_mm

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

    # [STATE Variables]
    current_chapter = 0
    previous_chapter = 0
    expected_page_str = None  # เลขหน้าที่ "ควรจะเป็น" ในรอบนี้

    current_chapter = 0

    for i, page in enumerate(doc, 1):
        w, h = page.rect.width, page.rect.height

        # Update Chapter
        previous_chapter = current_chapter
        current_chapter = detect_current_chapter(page, current_chapter)

        # เรียกฟังก์ชันดึงเลขหน้า
        page_num_str = get_page_number_text(page, m_top)

        is_first_page_of_chapter = False

        # เช็คว่าเป็นหน้าแรกของบทหรือไม่ (เปลี่ยนจากบทอื่น มาเป็นบท 1-5)
        is_first_page_of_chapter = (current_chapter != previous_chapter) and (1 <= current_chapter <= 9)

        # เช็คว่า: ตอนนี้อยู่บท 1 แล้ว (และก่อนหน้านี้ไม่ใช่บท 1)
        if is_first_page_of_chapter and current_chapter == 1:
            expected_page_str = "1"
            print(f"{YELLOW}>>> Entering Chapter 1: Resetting logical counter to '1'{RST}")

        # Sync (Init) ถ้ายังไม่มีเลขในใจ แต่เจอเลขบนกระดาษ -> เริ่มนับจากเลขที่เจอ
        if expected_page_str is None and page_num_str:
             expected_page_str = page_num_str

        expected_visible = expected_page_str  # ค่าปกติที่คาดหวังให้แสดงบนหน้า

        # Override: ถ้าเป็นหน้าแรกของบท ต้องไม่แสดงเลขหน้า (คาดหวัง None)
        if is_first_page_of_chapter:
            expected_visible = None
        
        
        # ---------------------------------------------------------
        # Print (Debug) - [UPDATED]
        # ---------------------------------------------------------
        display_text = page_num_str if page_num_str else "-"
        display_expect = expected_visible if expected_visible else "-"
        
        # เปรียบเทียบค่า: แปลงให้เป็น format เดียวกันก่อนเทียบ (None vs None)
        val_found = page_num_str if page_num_str else None
        val_expect = expected_visible
        
        # เลือกสี: ถ้าตรง=เขียว, ไม่ตรง=แดง
        if val_found == val_expect:
            status_color = GREEN
        else:
            status_color = RED

        print(f"Page {i}: Found Header = '{BLUE}{display_text}{RST}' expected_page : {status_color}{display_expect}{RST}")
        # ---------------------------------------------------------

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
            # แปลง Empty String เป็น None เพื่อให้เทียบง่ายๆ
            found_val = page_num_str if page_num_str else None
            
            # กรณีที่ 1: คาดหวังว่าจะ "ซ่อนเลข" (Expected Visible = None)
            if expected_visible is None:
                if found_val is not None:
                    # แต่ดันเจอเลขโผล่มา!
                    msg = f"รูปแบบหน้าผิด: หน้าแรกของบทต้องไม่แสดงเลขหน้า (เจอ '{found_val}')"
                    issues.append(Issue(i, "PAGE_SEQ_HIDDEN_ERR", "error", msg, bbox=[0,0,w,50]))

            # กรณีที่ 2: คาดหวังว่าจะ "มีเลข" (Expected Visible = "1", "2", ...)
            else:
                if found_val is None:
                    # หาเลขไม่เจอ
                    msg = f"ไม่พบเลขหน้า: ควรแสดงเลข '{expected_visible}'"
                    issues.append(Issue(i, "PAGE_SEQ_MISSING", "error", msg, bbox=[0,0,w,50]))
                
                elif found_val != expected_visible:
                    # เลขผิด (เช่น เจอ 5 แต่ควรเป็น 6)
                    msg = f"ลำดับหน้าผิด: เจอ '{found_val}' แต่ควรเป็น '{expected_visible}'"
                    issues.append(Issue(
                        i, "PAGE_SEQ_ERROR", "error", msg, 
                        bbox=fitz.Rect(w * 0.7, 0, w, m_top * 0.9)
                    ))
                    # Recovery: ผิดแล้วให้เชื่อตามเลขจริงไปเลย
                    expected_page_str = found_val

        # ---------------------------------------------------------
        # Calculate Next Page
        # ---------------------------------------------------------
        # เพื่อให้ State การนับหน้าทำงานต่อเนื่องเสมอ ไม่ว่าจะเปิดปิดการตรวจ
        if expected_page_str:
            expected_page_str = get_next_page_label(expected_page_str)
        elif page_num_str:
            # กรณีที่ expected หลุดไปแล้ว แต่กลับมาเจอเลขหน้าใหม่ ก็ให้เริ่มนับต่อจากตรงนี้
            expected_page_str = get_next_page_label(page_num_str)

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