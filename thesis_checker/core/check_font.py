from typing import List
from models import Issue

def check_font(page_num: int, spans: list, font_cfg: dict) -> List[Issue]:
    """
    ตรวจสอบกฎเกี่ยวกับฟอนต์ (ชื่อและขนาด)
    """
    found_issues = []
    
    # ดึงค่า Config มาเตรียมไว้
    font_keyword = font_cfg.get("name", "sarabun").lower()
    font_size_target = font_cfg.get("size", 16.0)
    font_tol = font_cfg.get("tolerance", 0.5)

    for span in spans:
        # ข้ามถ้าเป็นช่องว่างเปล่าๆ
        if not span["text"].strip(): continue
        
        # 1. ตรวจชื่อฟอนต์
        f_name = span["font"].lower()
        # อนุโลมให้ถ้ามีคำว่า cidfont (มักเป็นฟอนต์ระบบที่ฝังมา)
        if font_keyword not in f_name and "cidfont" not in f_name:
            found_issues.append(Issue(page_num, "FONT_NAME", f"ฟอนต์ผิด: {span['font']}", bbox=span["bbox"]))
        
        # 2. ตรวจขนาดฟอนต์ (เฉพาะช่วงขนาดที่สนใจ เช่น 10-20pt)
        if 10.0 <= span["size"] <= 20.0:
            if abs(span["size"] - font_size_target) > font_tol:
                found_issues.append(Issue(page_num, "FONT_SIZE", f"ขนาดผิด: {span['size']:.1f}pt", bbox=span["bbox"]))
                
    return found_issues