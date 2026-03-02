import fitz
import re
from typing import List

# Import models & config
from models import Issue
from config import load_config
from core.check_page_sequence import get_page_number_text, get_next_page_label
from utils import mm, to_mm

import utils as u

# Import Modular Checks
from core.check_margin import check_margin_rules
from core.check_font import check_font
from core.check_paper_size import check_paper_size
from core.check_indent import check_page_indentation
from core.check_section_sequence import check_section_rules

# Import Visual Checks
from core.check_img_table import get_visual_areas, is_inside_visual, check_visual_spacing
from core.detect_chapter import detect_current_chapter

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RST = '\033[0m'
RST = '\033[0m'

def run_all_checks(pdf_path: str) -> List[Issue]:
    doc = fitz.open(pdf_path)
    issues = []
    
    CFG = load_config()
    
    # Prepare Configurations
    checks = CFG.get("check_list", {})
    rules = CFG.get("indent_rules", {})

    # Pre-check paper size (A4)
    if checks.get("check_paper_size", False):
        paper_issues = check_paper_size(doc)
        if paper_issues:
            print(f"{RED}Pre-check Failed: Found {len(paper_issues)} paper size errors{RST}")
            return paper_issues
    
    font_cfg = CFG.get("font", {})
    margin_cfg = CFG.get("margin_mm", {})
    
    # Global Margins
    m_top = mm(margin_cfg.get("top", 25.4))
    m_bottom = mm(margin_cfg.get("bottom", 25.4))
    m_left = mm(margin_cfg.get("left", 38.1))
    
    expected_page_str = None

    # STATE Variables
    current_chapter = 0
    previous_chapter = 0
    last_section_nums = None  
    last_paren_num = None     
    expected_page_str = None  

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

        is_first_page_of_chapter = (current_chapter != previous_chapter) and (1 <= current_chapter <= 10)
        if is_first_page_of_chapter:
            last_section_nums = None  # รีเซ็ตเมื่อเข้าบทใหม่
            last_paren_num = None
        
        prev_line_memory = ""

        if is_first_page_of_chapter and current_chapter == 1:
            expected_page_str = "1"
            print(f"{YELLOW}>>> Entering Chapter 1: Resetting logical counter to '1'{RST}")

        # Sync (Init)
        if expected_page_str is None and page_num_str:
             expected_page_str = page_num_str

        expected_visible = expected_page_str
        if is_first_page_of_chapter:
            expected_visible = None

        # ไม่ต้องแสดงเลขหน้าในภาคผนวก ค   
        if current_chapter == 9:
            expected_visible = None
        
        # Print (Debug)
        display_text = page_num_str if page_num_str else "-"
        display_expect = expected_visible if expected_visible else "-"
        
        val_found = page_num_str if page_num_str else None
        val_expect = expected_visible
        
        status_color = GREEN if val_found == val_expect else RED
        print(f"Page {i}: Found Header = '{YELLOW}{display_text}{RST}' expected_page : {status_color}{display_expect}{RST}")

        # Re-detect chapter (เผื่อ header เปลี่ยนในหน้านั้น)
        current_chapter = detect_current_chapter(page, current_chapter)
        
        status_msg = f"Validating Page {i}"
        if current_chapter > 0:
            status_msg += f" (In Chapter {current_chapter})"
        else:
            status_msg += " (Pre-content / Abstract)"
        print(status_msg)
        print(f"  [STATE] last_paren_num={last_paren_num} | last_section_nums={last_section_nums}")        
        # Page Sequence
        if checks.get("check_page_seq"):
            found_val = page_num_str if page_num_str else None
            
            if expected_visible is None:
                if found_val is not None:
                    msg = f"รูปแบบหน้าผิด: หน้าแรกของบทต้องไม่แสดงเลขหน้า (เจอ '{found_val}')"
                    issues.append(Issue(i, "PAGE_SEQ_HIDDEN_ERR", msg, bbox=[w*0.7, 0, w, m_top*0.9]))
            else:
                if found_val is None:
                    msg = f"ไม่พบเลขหน้า: ควรแสดงเลข '{expected_visible}'"
                    issues.append(Issue(i, "PAGE_SEQ_MISSING", msg, bbox=[w*0.7, 0, w, m_top*0.9]))
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

        # ตรวจ Indentation แบบ Block
        is_main_content = (1 <= current_chapter <= 5)
        
        if checks.get("check_indentation") and is_main_content:
            indent_issues = check_page_indentation(page, i, m_left, rules, visual_rects)
            issues.extend(indent_issues)

        # เตรียมข้อมูล Text Blocks ของทั้งหน้า
        text_data = page.get_text("dict")
        all_lines = []
        for block in text_data["blocks"]:
            # กรองเฉพาะ Text ไม่เอารูปภาพ
            if block.get("type") != 0: continue
            if "lines" in block:
                for line in block["lines"]:
                    all_lines.append(line)
        
        all_lines.sort(key=lambda l: l["bbox"][1])

        # กรองข้อมูลบรรทัดที่จะนำไปตรวจจับ (เอา Header/Footer และรูปภาพ/ตาราง ออก)
        content_lines_for_margin = []

        for line in all_lines:
            l_bbox = fitz.Rect(line["bbox"])
            
            if l_bbox.y1 < m_top or l_bbox.y0 > (h - m_bottom): 
                continue

            if is_inside_visual(line["bbox"], visual_rects):
                continue

            spans = line["spans"]
            line_text = "".join([s["text"] for s in spans]).strip()
            if not line_text: 
                continue
                
            content_lines_for_margin.append(line)

            # ตรวจลำดับหัวข้อ (เฉพาะบท 1-5)
            if checks.get("check_section_seq") and is_main_content:
                sec_match = re.match(r"^(\d+(?:\.\d+)*\.?)", line_text.strip())
                if sec_match:
                    sec_text = sec_match.group(1)
                    first_span = spans[0]
                    s_bbox = list(first_span["bbox"])  # [x0, y0, x1, y1]
                    span_text = first_span["text"]
                    if len(span_text) > 0:
                        ratio = min(len(sec_text) / len(span_text), 1.0)
                        sec_bbox = [s_bbox[0], s_bbox[1], s_bbox[0] + (s_bbox[2] - s_bbox[0]) * ratio, s_bbox[3]]
                    else:
                        sec_bbox = s_bbox
                else:
                    sec_bbox = line["bbox"]

                sec_issues, last_section_nums, last_paren_num = check_section_rules(
                    page_num=i,
                    line_text=line_text,
                    bbox=sec_bbox,
                    chapter_num=current_chapter,
                    last_section_nums=last_section_nums,
                    last_paren_num=last_paren_num,
                    ignored_units=CFG.get("ignored_units", []),
                    prev_line_text=prev_line_memory
                )
                issues.extend(sec_issues)

                if line_text.strip():
                    prev_line_memory = line_text

            if checks.get("check_font"):
                font_issues = check_font(
                    page_num=i, 
                    spans=spans, 
                    font_cfg=font_cfg
                )
                issues.extend(font_issues)

        if checks.get("check_margin") and content_lines_for_margin:
            margin_issues = check_margin_rules(
                page_num=i, 
                page_elements=content_lines_for_margin,
                margin_cfg=margin_cfg,
                page_width=w,
                page_height=h
            )
            issues.extend(margin_issues)

    return issues