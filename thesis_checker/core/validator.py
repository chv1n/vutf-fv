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
from core.check_paper_size import check_paper_size
from core.check_indent import check_page_indentation

# Import Visual Checks
from core.check_img_table import get_visual_areas, is_inside_visual, check_visual_spacing
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

    for i, page in enumerate(doc, 1):
        w, h = page.rect.width, page.rect.height

        # Detect Tables & Images (Visual Areas)
        visual_rects = get_visual_areas(page)

        # Check Spacing Before Tables/Images
        if checks.get("check_spacing", True): 
             spacing_issues = check_visual_spacing(i, page, visual_rects, min_gap_mm=8.0)
             issues.extend(spacing_issues)

        # Update Chapter
        previous_chapter = current_chapter
        current_chapter = detect_current_chapter(page, current_chapter)

        # เรียกฟังก์ชันดึงเลขหน้า
        page_num_str = get_page_number_text(page, m_top)

        is_first_page_of_chapter = (current_chapter != previous_chapter) and (1 <= current_chapter <= 9)

        if is_first_page_of_chapter and current_chapter == 1:
            expected_page_str = "1"
            print(f"{YELLOW}>>> Entering Chapter 1: Resetting logical counter to '1'{RST}")

        # Sync (Init)
        if expected_page_str is None and page_num_str:
             expected_page_str = page_num_str

        expected_visible = expected_page_str
        if is_first_page_of_chapter:
            expected_visible = None
        
        # Print (Debug)
        display_text = page_num_str if page_num_str else "-"
        display_expect = expected_visible if expected_visible else "-"
        
        val_found = page_num_str if page_num_str else None
        val_expect = expected_visible
        
        status_color = GREEN if val_found == val_expect else RED
        print(f"Page {i}: Found Header = '{BLUE}{display_text}{RST}' expected_page : {status_color}{display_expect}{RST}")

        # Re-detect chapter (เผื่อ header เปลี่ยนในหน้านั้น)
        current_chapter = detect_current_chapter(page, current_chapter)
        
        status_msg = f"Validating Page {i}"
        if current_chapter > 0:
            status_msg += f" (In Chapter {current_chapter})"
        else:
            status_msg += " (Pre-content / Abstract)"
        print(status_msg)
        
        # --- A. Page Sequence ---
        if checks.get("check_page_seq"):
            found_val = page_num_str if page_num_str else None
            
            if expected_visible is None:
                if found_val is not None:
                    msg = f"รูปแบบหน้าผิด: หน้าแรกของบทต้องไม่แสดงเลขหน้า (เจอ '{found_val}')"
                    issues.append(Issue(i, "PAGE_SEQ_HIDDEN_ERR", msg, bbox=[0,0,w,50]))
            else:
                if found_val is None:
                    msg = f"ไม่พบเลขหน้า: ควรแสดงเลข '{expected_visible}'"
                    issues.append(Issue(i, "PAGE_SEQ_MISSING", msg, bbox=[0,0,w,50]))
                elif found_val != expected_visible:
                    msg = f"ลำดับหน้าผิด: เจอ '{found_val}' แต่ควรเป็น '{expected_visible}'"
                    issues.append(Issue(
                        i, "PAGE_SEQ_ERROR", msg, 
                        bbox=fitz.Rect(w * 0.7, 0, w, m_top * 0.9)
                    ))
                    expected_page_str = found_val

        if expected_page_str:
            expected_page_str = get_next_page_label(expected_page_str)
        elif page_num_str:
            expected_page_str = get_next_page_label(page_num_str)

        # ตรวจ Indentation แบบ Block (ดึงออกมาตรวจรอบเดียวทั้งหน้า)
        is_main_content = (1 <= current_chapter <= 5)
        
        if checks.get("check_indentation") and is_main_content:
            # โยนตัวแปรให้ฟังก์ชันใหม่จัดการทีเดียวทั้งหน้าเลย (มี visual_rects ส่งไปให้กันพลาดตรวจในรูปด้วย)
            indent_issues = check_page_indentation(page, i, m_left, rules, visual_rects)
            issues.extend(indent_issues)

        # Line Loop (ตรวจเฉพาะ Margin กับ Font ทีละบรรทัด) ---
        text_data = page.get_text("dict")
        all_lines = []
        for block in text_data["blocks"]:
            # กรองเฉพาะ Text ไม่เอารูปภาพ
            if block.get("type") != 0: continue
            if "lines" in block:
                for line in block["lines"]:
                    all_lines.append(line)
        
        all_lines.sort(key=lambda l: l["bbox"][1])

        for line in all_lines:
            l_bbox = fitz.Rect(line["bbox"])
            
            # Filter Header/Footer
            if l_bbox.y1 < m_top or l_bbox.y0 > (h - m_bottom): continue

            # Visual Content Filtering (ข้ามตารางและรูปภาพ)
            if is_inside_visual(line["bbox"], visual_rects):
                continue

            spans = line["spans"]
            line_text = "".join([s["text"] for s in spans]).strip()
            if not line_text: continue
            
            # 1. Margin (ยังต้องใช้ลูปทีละบรรทัดอยู่ เผื่อมีบางบรรทัดทะลุขอบ)
            if checks.get("check_margin"):
                margin_issues = check_margin_rules(
                    page_num=i, 
                    bbox=line["bbox"], 
                    margin_cfg=margin_cfg,
                    page_width=w,
                    page_height=h,  
                    spans=line["spans"] 
                )
                issues.extend(margin_issues)

            # 2. Font (ยังต้องใช้ลูปเช็คทุกคำ เพื่อกันเปลี่ยนฟอนต์กลางประโยค)
            if checks.get("check_font"):
                font_issues = check_font(
                    page_num=i, 
                    spans=spans, 
                    font_cfg=font_cfg
                )
                issues.extend(font_issues)

    return issues