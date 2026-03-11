import fitz
from tqdm import tqdm
from typing import List

# Import models & config
from models import Issue, ThesisState
from config import load_config, DEBUG_LINE, NO_PAGE_SECTIONS
from core.check_page_sequence import check_page_sequence
from utils import mm_to_pt

# Import Modular Checks
from core.check_margin import check_margin_rules
from core.check_font import check_font
from core.check_paper_size import check_paper_size
from core.check_indent import check_page_indentation
from core.check_section_sequence import check_section_sequence

# Import Utility
from core.check_utils import get_prefix_and_text_coords
from core.debug_line import debug_line

# Import Visual Checks
from core.check_img_table import get_visual_areas, is_inside_visual, check_visual_spacing
from core.detect_chapter import detect_current_chapter

def _span_text(span: dict) -> str:
    if "text" in span: return span["text"]
    if "chars" in span: return "".join(ch.get("c", "") for ch in span["chars"])
    return ""

def run_all_checks(pdf_path: str) -> List[Issue]:
    doc = fitz.open(pdf_path)
    issues = []
    global_state = ThesisState()
    
    # ตรวจสอบขนาดกระดาษ (ตรวจครั้งเดียวทั้งไฟล์)
    paper_issues = check_paper_size(doc)
    if paper_issues:
        issues.extend(paper_issues)

    CFG = load_config()
    checks = CFG.get("check_list", {})
    rules = CFG.get("indent_rules", {})
    font_cfg = CFG.get("font", {})
    margin_cfg = CFG.get("margin_mm", {})
    ignored_units = CFG.get("ignored_units", [])
    
    m_top = mm_to_pt(margin_cfg.get("top", 25.4))
    m_bottom = mm_to_pt(margin_cfg.get("bottom", 25.4))
    m_left = mm_to_pt(margin_cfg.get("left", 38.1))
    
    current_chapter, previous_chapter = 0, 0
    expected_page_str = None
    
    _debug_file = open("debug_output_data.ans", "w", encoding="utf-8") if DEBUG_LINE else None

    for i, page in enumerate(tqdm(doc, desc="validate", unit="page", total=len(doc)), 1):
        w, h = page.rect.width, page.rect.height
        visual_rects = get_visual_areas(page)
        
        # กรองโซนเลขหน้า (มุมขวาบน)
        page_num_rect = fitz.Rect(w * 0.7, 0, w, h * 0.1)

        if checks.get("check_spacing", True): 
             issues.extend(check_visual_spacing(i, page, visual_rects))

        previous_chapter = current_chapter
        current_chapter = detect_current_chapter(page, current_chapter)

        # ตรวจสอบลำดับเลขหน้า
        page_seq_issues, expected_page_str, page_num_str = check_page_sequence(
            page_index=i, page=page, current_chapter=current_chapter,
            previous_chapter=previous_chapter, expected_page_str=expected_page_str,
            m_top=m_top, enabled=checks.get("check_page_seq", True),
        )
        issues.extend(page_seq_issues)

        is_first_page_of_chapter = (current_chapter != previous_chapter)
        if is_first_page_of_chapter and (current_chapter in NO_PAGE_SECTIONS):
            global_state.reset_for_new_chapter()

        is_main_content = (1 <= current_chapter <= 5)

        # ดึงข้อมูลบรรทัดและเรียงลำดับ
        text_data = page.get_text("rawdict")
        raw_lines = []
        for block in text_data.get("blocks", []):
            if block.get("type") != 0: continue
            for line in block.get("lines", []): raw_lines.append(line)
            
        # เรียง Y (บนลงล่าง) แล้วค่อยเรียง X (ซ้ายไปขวา)
        raw_lines.sort(key=lambda l: (l["bbox"][1], l["bbox"][0]))

        # รวมบรรทัดที่ถูกหั่น
        all_lines = []
        if raw_lines:
            current_line = raw_lines[0]
            for next_line in raw_lines[1:]:
                y_diff = abs(current_line["bbox"][1] - next_line["bbox"][1])
                if y_diff < 5.0: # ถ้าอยู่บรรทัดเดียวกัน
                    current_line["spans"].extend(next_line["spans"])
                    x0 = min(current_line["bbox"][0], next_line["bbox"][0])
                    y0 = min(current_line["bbox"][1], next_line["bbox"][1])
                    x1 = max(current_line["bbox"][2], next_line["bbox"][2])
                    y1 = max(current_line["bbox"][3], next_line["bbox"][3])
                    current_line["bbox"] = (x0, y0, x1, y1)
                else:
                    all_lines.append(current_line)
                    current_line = next_line
            all_lines.append(current_line)

        # ตรวจ Indent
        if checks.get("check_indentation") and is_main_content:
            issues.extend(check_page_indentation(
                global_state, all_lines, i, m_left, rules, 
                visual_rects, ignored_units, 
                page_num_rect=page_num_rect
            ))

        # ตรวจ Margin, Font และ Sequence
        content_lines_for_margin = []

        for line in all_lines:
            l_bbox = fitz.Rect(line["bbox"])

            # ไม่ตรวจเลขหน้า และ ส่วนที่อยู่นอกขอบบน/ล่าง
            if l_bbox.intersects(page_num_rect): 
                continue
            if l_bbox.y1 < m_top or l_bbox.y0 > (h - m_bottom): 
                continue
            if is_inside_visual(line["bbox"], visual_rects): 
                continue

            spans = line.get("spans", [])
            line_text = "".join([_span_text(s) for s in spans]).strip()
            if not line_text: 
                continue

            if DEBUG_LINE and _debug_file and line_text:
                msg = debug_line(i, line_text, line, current_chapter)
                if msg:
                    _debug_file.write(msg + "\n")
            
            # เก็บไว้ตรวจ Margin ท้ายหน้า
            content_lines_for_margin.append(line)

            # ตรวจ Sequence (ลำดับหัวข้อ)
            if checks.get("check_section_seq") and is_main_content:
                prefix_data = get_prefix_and_text_coords(line)
                line_type = prefix_data["type"]
                prefix_str = prefix_data["prefix"]

                if line_type in ["section", "sub_section", "sub_sub_section"]:
                    seq_error = check_section_sequence(global_state, current_chapter, line_type, prefix_str, line_text, ignored_units)
                    if seq_error:
                        result = get_prefix_and_text_coords(line)
                        prefix_x0 = result["prefix_x0"]
                        trimmed_bbox = (prefix_x0, line["bbox"][1], line["bbox"][2], line["bbox"][3])
                        issues.append(Issue(page=i, code="SECTION_SEQ_ERROR", message=seq_error, bbox=trimmed_bbox))

            # ตรวจ Font
            if checks.get("check_font"):
                issues.extend(check_font(i, spans, font_cfg))

            # อัปเดต State
            global_state.update_prev_text(line_text)
            global_state.prev_line_x1 = line["bbox"][2]

        # ตรวจ Margin
        if checks.get("check_margin") and content_lines_for_margin:
            issues.extend(check_margin_rules(i, content_lines_for_margin, margin_cfg, w, h))

    if _debug_file: _debug_file.close()
    return issues