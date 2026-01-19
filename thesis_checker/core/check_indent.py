from typing import List
from models import Issue
from utils import to_mm, parse_sub_section_bullet

def check_indentation_rules(
    page_num: int,
    line_text: str,
    spans: list,
    bbox: list,      # line["bbox"]
    dist_mm: float,  # ระยะห่างจากขอบซ้าย (คำนวณมาแล้ว)
    rules: dict,     # config["indent_rules"]
    m_left: float    # margin left
) -> List[Issue]:
    
    found_issues = []

    # 1. ตรวจสอบหัวข้อย่อย (เช่น 1), 1.1) )
    digits = parse_sub_section_bullet(line_text)
    if digits:
        # --- 1.1 ตรวจระยะตัวเลข (Sub-section Number) ---
        target_num = rules["sub_section_num"]
        if abs(dist_mm - target_num) > rules["tolerance"]:
            msg = f"เยื้องเลขหัวข้อผิด: {dist_mm:.1f}mm (ค่าที่กำหนด: {target_num}mm)"
            found_issues.append(Issue(page_num, "INDENT_ERR", msg, bbox=bbox))
        
        # --- 1.2 ตรวจระยะชื่อหัวข้อ (Text) ---
        if len(spans) > 1:
            # span[0] คือเลขข้อ, span[1] คือเนื้อหา
            text_dist = to_mm(spans[1]["bbox"][0] - m_left)
            
            # ถ้าเลข 1 หลัก (1) ) -> ระยะ 25mm
            # ถ้าเลข 2 หลัก (10) ) -> ระยะ 27.6mm
            target_text = rules["sub_section_text_1"] if digits == 1 else rules["sub_section_text_2"]
            
            if abs(text_dist - target_text) > rules["tolerance"]:
                msg = f"ชื่อหัวข้อย่อยเริ่มผิดตำแหน่ง: {text_dist:.1f}mm (ค่าที่กำหนด: {target_text}mm)"
                found_issues.append(Issue(page_num, "TEXT_ALIGN_ERR", msg, bbox=spans[1]["bbox"]))

    # 2. ตรวจสอบ Bullet (•)
    elif "•" in line_text:
        target_bullet = rules["bullet_point"]
        if abs(dist_mm - target_bullet) > rules["tolerance"]:
            msg = f"จุด Bullet เยื้องผิด: {dist_mm:.1f}mm (ค่าที่กำหนด: {target_bullet}mm)"
            found_issues.append(Issue(page_num, "BULLET_ERR", msg, bbox=bbox))

    return found_issues