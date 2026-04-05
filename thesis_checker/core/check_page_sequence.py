import fitz
import re
from typing import List, Optional
from models import Issue

def get_page_number_text(page, margin_top: float) -> str:
    w = page.rect.width
    header_rect = fitz.Rect(w * 0.7, 0, w, margin_top * 0.9)
    
    # ดึง text ออกมา
    raw_text = page.get_text("text", clip=header_rect).strip()
    
    # ป้องกันกรณีมีคำว่า "หน้า", "Page" หรือชื่อบทติดมา
    match = re.search(r"([0-9๐-๙]+|[ก-ฮ])", raw_text)
    if match:
        return match.group(1)
    
    return ""

def get_next_page_label(current_label: str) -> str:
    current_label = current_label.strip()
    if not current_label: return ""

    thai_digits = "๐๑๒๓๔๕๖๗๘๙"
    arabic_digits = "0123456789"
    
    # เช็คว่าเป็นเลขไทยไหม
    if all(c in thai_digits for c in current_label):
        # แปลง ไทย -> อารบิก -> บวกหนึ่ง -> แปลงกลับเป็นไทย
        trans = str.maketrans(thai_digits, arabic_digits)
        num = int(current_label.translate(trans)) + 1
        back_trans = str.maketrans(arabic_digits, thai_digits)
        return str(num).translate(back_trans)

    if current_label.isdigit():
        return str(int(current_label) + 1)
    
    thai_seq = "กขคคงจฉชซญดตถทธนบปผฝพฟภมยรลวศษสหอ" 
    if current_label in thai_seq:
        idx = thai_seq.index(current_label)
        if idx + 1 < len(thai_seq):
            return thai_seq[idx + 1]
            
    return ""


def check_page_sequence(
    page_index: int,
    page,
    current_chapter: int,
    previous_chapter: int,
    expected_page_str: Optional[str],
    m_top: float,
    enabled: bool = True,
) -> tuple:
    """
    ตรวจสอบลำดับเลขหน้าของหน้าปัจจุบัน
    """
    w = page.rect.width
    issues: List[Issue] = []

    page_num_str = get_page_number_text(page, m_top)

    # ซ่อนเลขหน้าหน้าแรก
    NO_PAGE_SECTIONS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
    
    is_first_page_of_chapter = (current_chapter != previous_chapter) and (current_chapter in NO_PAGE_SECTIONS)

    if is_first_page_of_chapter and current_chapter == 1:
        expected_page_str = "1"

    if expected_page_str is None and page_num_str:
        expected_page_str = page_num_str
    expected_visible = None if is_first_page_of_chapter else expected_page_str

    if enabled and current_chapter != 0:
        found_val = page_num_str if page_num_str else None
        if expected_visible is None:
            if found_val:
                issues.append(Issue(
                    page=page_index, code="PAGE_SEQ_HIDDEN_ERR",
                    message="หน้าแรกของบทต้องไม่แสดงเลขหน้า",
                    bbox=[w * 0.7, 0, w, m_top], severity="error"
                ))
        elif found_val != expected_visible:
            issues.append(Issue(
                page=page_index, code="PAGE_SEQ_ERROR",
                message=f"ลำดับหน้าผิด: เจอ '{found_val}' ควรเป็น '{expected_visible}'",
                bbox=[w * 0.7, 0, w, m_top], severity="error"
            ))
            expected_page_str = found_val

    if expected_page_str:
        expected_page_str = get_next_page_label(expected_page_str)

    return issues, expected_page_str, page_num_str