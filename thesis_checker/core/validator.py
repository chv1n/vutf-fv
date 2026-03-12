import fitz
import re
from tqdm import tqdm
from typing import List

# Import models & config
from models import Issue, ThesisState
from config import load_config, DEBUG_LINE, NO_PAGE_SECTIONS
from core.check_page_sequence import check_page_sequence
from utils import mm, to_mm

# Import Modular Checks
from core.check_margin import check_margin_rules
from core.check_font import check_font
from core.check_paper_size import check_paper_size
from core.check_indent import check_page_indentation
from core.check_section_sequence import check_section_sequence

# Import Utility
from core.check_utils import get_prefix_and_text_coords, is_formula
from core.debug_line import debug_line

# Import Visual Checks
from core.check_img_table import get_visual_areas, is_inside_visual, check_visual_spacing
from core.detect_chapter import detect_current_chapter

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RST = '\033[0m'

ENFORCE_A4_SIZE = False

def _span_text(span: dict) -> str:
    """ดึงข้อความจาก span ไม่ว่าจะเป็น dict หรือ rawdict"""
    if "text" in span:
        return span["text"]
    if "chars" in span:
        return "".join(ch.get("c", "") for ch in span["chars"])
    return ""

def run_all_checks(pdf_path: str) -> List[Issue]:
    doc = fitz.open(pdf_path)
    issues = []
    global_state = ThesisState()
    
    # ตรวจสอบขนาดกระดาษ
    paper_issues = check_paper_size(doc)
    if paper_issues and ENFORCE_A4_SIZE:
        return paper_issues

    CFG = load_config()
    checks = CFG.get("check_list", {})
    rules = CFG.get("indent_rules", {})
    font_cfg = CFG.get("font", {})
    margin_cfg = CFG.get("margin_mm", {})
    ignored_units = CFG.get("ignored_units", [])
    
    m_top = mm(margin_cfg.get("top", 25.4))
    m_bottom = mm(margin_cfg.get("bottom", 25.4))
    m_left = mm(margin_cfg.get("left", 38.1))
    m_right = mm(margin_cfg.get("right", 25.4))
    
    # ตัวแปรสำหรับเก็บสถานะ
    current_chapter, previous_chapter = 0, 0
    expected_page_str = None
    
    _debug_file = open("debug_output_data.ans", "w", encoding="utf-8") if DEBUG_LINE else None

    # loop แต่ละหน้า
    for i, page in enumerate(tqdm(doc, desc="validate", unit="page", total=len(doc)), 1):
        if _debug_file:
            _debug_file.write(f"\n--- Page {i} ---\n")
        w, h = page.rect.width, page.rect.height
        visual_rects = get_visual_areas(page)

        if checks.get("check_spacing", True): 
             issues.extend(check_visual_spacing(i, page, visual_rects))

        previous_chapter = current_chapter
        current_chapter = detect_current_chapter(page, current_chapter)

        # ตรวจสอบลำดับเลขหน้า
        page_seq_issues, expected_page_str, page_num_str = check_page_sequence(
            page_index=i,
            page=page,
            current_chapter=current_chapter,
            previous_chapter=previous_chapter,
            expected_page_str=expected_page_str,
            m_top=m_top,
            enabled=checks.get("check_page_seq", True),
        )
        issues.extend(page_seq_issues)

        is_first_page_of_chapter = (current_chapter != previous_chapter)

        text_data = page.get_text("rawdict")
        all_lines = []
        for block in text_data.get("blocks", []):
            if block.get("type") != 0: continue
            for line in block.get("lines", []):
                all_lines.append(line)
        all_lines.sort(key=lambda l: l["bbox"][1])

        
        if is_first_page_of_chapter and (current_chapter in NO_PAGE_SECTIONS):
            global_state.reset_for_new_chapter()

        is_main_content = (1 <= current_chapter <= 5)

        # Indent Check 
        if checks.get("check_indentation") and is_main_content:
            issues.extend(check_page_indentation(global_state, page, i, m_left, rules, visual_rects, ignored_units))

        content_lines_for_margin = []
        prev_l_bbox_for_seq = None  # เก็บพิกัดบรรทัดก่อนหน้า

        for line in all_lines:
            l_bbox = fitz.Rect(line["bbox"])

            if l_bbox.y1 < m_top or l_bbox.y0 > (h - m_bottom): 
                continue
            if is_inside_visual(line["bbox"], visual_rects): 
                continue

            spans = line.get("spans", [])
            # ดึงข้อความจาก span
            line_text = "".join([_span_text(s) for s in spans]).strip()

            # DEBUG: แต่ละ line
            if DEBUG_LINE and _debug_file and line_text:
                msg = debug_line(i, line_text, line, current_chapter)
                if msg:
                    _debug_file.write(msg + "\n")
            
            # if not line_text or 0 < len(line_text) <= 3 or is_formula(line_text) or line_text.startswith("เมื่อ"): 
            #     continue

            content_lines_for_margin.append(line)

            prefix_data = get_prefix_and_text_coords(line)
            b_type = prefix_data["type"]
            prefix_str = prefix_data["prefix"]
            
            prefix_x0 = prefix_data.get("prefix_x0")
            text_x0 = prefix_data.get("text_x0")
            
            dist_mm = to_mm(prefix_x0 - m_left) if prefix_x0 is not None else None
            text_dist_mm = to_mm(text_x0 - m_left) if text_x0 is not None else None

            # ---------------------- กรองหัวข้อปลอม ----------------------
            if dist_mm is not None and text_dist_mm is not None:
                is_fake = False
                
                # เช็คระยะห่างระหว่างบรรทัด (ใช้ y0 - y0 จะแม่นยำกว่า y0 - y1)
                # ปกติถ้าเว้น 1 บรรทัด ระยะ y0 จะห่างกันประมาณ 40pt+ ถ้าบรรทัดติดกันจะห่างแค่ ~20-25pt
                gap_y0 = (l_bbox.y0 - prev_l_bbox_for_seq.y0) if prev_l_bbox_for_seq else 100.0
                is_continuous = gap_y0 < 35.0  # ถ้า < 35.0 แปลว่าไม่มีบรรทัดว่างคั่น
                
                if b_type == "section":
                    # กฎ 1: บรรทัดติดกัน + ระยะข้อความไม่ถึง 8mm (ไม่ได้กด Tab) = ย่อหน้าตัดคำ
                    if is_continuous and text_dist_mm < 8.0:
                        is_fake = True
                    # กฎ 2: เยื้องลึกเกินไป
                    elif dist_mm > 15.0:
                        is_fake = True
                        
                elif b_type == "sub_section":
                    # กฎ 1: บรรทัดติดกัน + ตัวเลขเกาะขอบซ้ายสุด (< 5mm) = ย่อหน้าตัดคำ
                    if is_continuous and dist_mm < 5.0:
                        is_fake = True
                    # กฎ 2: เยื้องลึกเกินไป
                    elif dist_mm > 20.0:
                        is_fake = True
                        
                if is_fake:
                    b_type = "paragraph"
                    prefix_str = ""
            # --------------------------------------------------------
            
            # ถ้าเจอหัวข้อที่ลึกเกิน 3 ระดับ แจ้ง Error ทันที
            if b_type == "invalid_heading":
                issues.append(Issue(
                    page=i, 
                    code="INVALID_HEADING_LEVEL", 
                    message=f"รูปแบบผิด: ห้ามใช้หัวข้อย่อยเกิน 3 ระดับ ({prefix_str}) ให้เปลี่ยนไปใช้รายการย่อย 1) แทน", 
                    bbox=line["bbox"], 
                    severity="error"
                ))
                continue # ข้ามบรรทัดนี้ไปเลย ไม่ต้องเอาไปเช็ค Sequence หรือ Indent ต่อ

            # Sequence Check
            if checks.get("check_section_seq") and is_main_content:
                if b_type in ["section", "sub_section", "sub_sub_section"]:
                    
                    # ถ้าข้อความเป็นสมการ หรือสั้นเกินไป (เช่น "2)") ให้ข้ามไป ไม่ต้องนับลำดับ
                    if is_formula(line_text) or len(line_text.strip()) <= 3:
                        continue
                    
                    seq_error = check_section_sequence(global_state, current_chapter, b_type, prefix_str, line_text, ignored_units)
                    
                    if seq_error:
                        sec_match = re.match(r"^(\d+(?:\.\d+)*\.?)", line_text)
                        sec_bbox = line["bbox"]
                        if sec_match and spans:
                            s_txt = _span_text(spans[0])
                            if s_txt:
                                ratio = min(len(sec_match.group(1)) / len(s_txt), 1.0)
                                s_bbox = spans[0]["bbox"]
                                sec_bbox = [s_bbox[0], s_bbox[1], s_bbox[0] + (s_bbox[2]-s_bbox[0])*ratio, s_bbox[3]]

                        issues.append(Issue(
                            page=i, code="SECTION_SEQ_ERR", message=seq_error, bbox=sec_bbox, severity="error"
                        ))
                        
            global_state.update_prev_text(line_text)

            if checks.get("check_font"):
                issues.extend(check_font(i, spans, font_cfg))
                
            # อัปเดตพิกัดบรรทัดก่อนหน้า
            prev_l_bbox_for_seq = l_bbox

        if checks.get("check_margin") and content_lines_for_margin:
            issues.extend(check_margin_rules(i, content_lines_for_margin, margin_cfg, w, h))

    if _debug_file:
        _debug_file.close()
    return issues