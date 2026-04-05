import re
from typing import List
from models import Issue
from config import WARNING_FONTS, IGNORED_SYMBOLS, MATH_FONTS, NUMERIC_PATTERN, LATIN_VAR_PATTERN, GREEK_SYMBOLS


def check_font(page_num: int, spans: list, font_cfg: dict) -> List[Issue]:
    """
    ตรวจสอบกฎเกี่ยวกับฟอนต์
    """
    found_issues = []
    
    font_keyword = font_cfg.get("name", "sarabun").lower()
    font_size_target = font_cfg.get("size", 16.0)
    font_tol = font_cfg.get("tolerance", 0.5)

    for span in spans:
        if "text" in span:
            text_content = span["text"].strip()
        elif "chars" in span:
            # ถ้าเป็น rawdict ให้ประกอบ str จาก list ของตัวอักษร
            text_content = "".join([ch.get("c", "") for ch in span["chars"]]).strip()
        else:
            continue

        span_size = span["size"]
        f_name_lower = span["font"].lower()

        if not text_content: 
            continue
        if text_content in IGNORED_SYMBOLS: 
            continue
        if any(m in f_name_lower for m in MATH_FONTS): 
            continue
        if any(g in text_content for g in GREEK_SYMBOLS): 
            continue
        if re.match(NUMERIC_PATTERN, text_content):
            if span_size < (font_size_target - 1.0): 
                continue
        if re.match(LATIN_VAR_PATTERN, text_content): 
            continue

        # ตรวจชื่อฟอนต์
        if font_keyword not in f_name_lower and "cidfont" not in f_name_lower and "cordia" not in f_name_lower:
            if any(wf in f_name_lower for wf in WARNING_FONTS):
                severity = "warning"
                msg = f"ฟอนต์ภายในเป็น {span['font']} (อนุโลม)"
            else:
                severity = "error"
                msg = f"ฟอนต์ผิดระเบียบ: {span['font']} (ต้องเป็น Sarabun)"

            found_issues.append(Issue(
                page=page_num, code="FONT_NAME", severity=severity, 
                message=msg, bbox=span["bbox"]
            ))
        
        # ตรวจขนาดฟอนต์
        if 12.0 <= span_size <= 20.0:
            if abs(span_size - font_size_target) > font_tol:
                found_issues.append(Issue(
                    page=page_num, code="FONT_SIZE", severity="warning", 
                    message=f"ขนาดผิด: {span_size:.1f}pt (เจอ '{text_content}')", 
                    bbox=span["bbox"]
                ))
                
    return found_issues