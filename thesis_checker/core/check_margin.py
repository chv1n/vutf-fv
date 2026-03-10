import fitz
from typing import List, Dict, Any
from models import Issue
from utils import to_mm

def check_margin_rules(
    page_num: int, 
    page_elements: List[Dict[str, Any]], 
    margin_cfg: dict, 
    page_width: float, 
    page_height: float
) -> List[Issue]:
    issues = []
    
    m_top = to_mm(margin_cfg.get("top", 25.4))
    m_bottom = to_mm(margin_cfg.get("bottom", 25.4))
    m_left = to_mm(margin_cfg.get("left", 38.1))
    m_right = to_mm(margin_cfg.get("right", 25.4))
    
    TOLERANCE = 2.0
    limit_right = page_width - m_right
    limit_bottom = page_height - m_bottom

    for element in page_elements:
        # ดึงตัวอักษรทั้งหมดออกมาเป็น Flat List (Rawdict Support)
        all_chars = []
        for span in element.get("spans", []):
            if "chars" in span:
                all_chars.extend(span["chars"])
            elif "text" in span: # Fallback สำหรับ dict ปกติ
                # ถ้าเป็น dict ปกติ เราจะไม่มีพิกัดแยกตัวอักษร ต้องใช้ bbox span แทน
                # แต่ในเคสพี่ตอนนี้เป็น rawdict หมดแล้ว
                pass

        if not all_chars:
            continue

        # หา Index ของตัวอักษรที่ไม่ใช่ช่องว่างตัวแรกและตัวสุดท้าย (Trim Logic)
        non_space_indices = [
            i for i, char in enumerate(all_chars) 
            if char.get("c", "").strip() # เช็คว่าเป็นตัวหนังสือ ไม่ใช่ Space/Tab
        ]

        if not non_space_indices:
            continue # บรรทัดนี้มีแต่ช่องว่าง ข้ามไปเลย

        first_idx = non_space_indices[0]
        last_idx = non_space_indices[-1]

        # คำนวณ Bbox ใหม่จากตัวอักษรที่ผ่านการ Trim แล้ว
        real_rect = fitz.Rect()
        for i in range(first_idx, last_idx + 1):
            real_rect.include_rect(all_chars[i]["bbox"])

        real_x0, real_y0, real_x1, real_y1 = real_rect

        # ตรวจสอบ Margin (ใช้พิกัดที่ผ่านการ Trim แล้ว)
        
        # ตรวจขอบซ้าย
        if real_x0 < (m_left - TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_LEFT", severity="error", 
                message=f"เนื้อหาล้นขอบซ้าย: ล้ำเข้าไปที่ {to_mm(real_x0):.1f} mm (ขอบคือ {to_mm(m_left):.1f} mm)", 
                bbox=[real_x0, real_y0, m_left, real_y1] 
            ))

        # ตรวจขอบขวา
        if real_x1 > (limit_right + TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_RIGHT", severity="error", 
                message=f"เนื้อหาล้นขอบขวา: ล้ำไปที่ {to_mm(real_x1):.1f} mm (ขอบคือ {to_mm(limit_right):.1f} mm)", 
                bbox=[limit_right, real_y0, real_x1, real_y1] 
            ))

       # ตรวจขอบล่าง
        if real_y1 > (limit_bottom + TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_BOTTOM", severity="error", 
                message=f"เนื้อหาล้นขอบล่าง: ล้ำไปที่ {to_mm(real_y1):.1f} mm (ขอบคือ {to_mm(limit_bottom):.1f} mm)", 
                bbox=[real_x0, limit_bottom, real_x1, real_y1] 
            ))

        # ตรวจขอบบน
        if real_y0 < (m_top - TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_TOP", severity="error", 
                message=f"เนื้อหาล้นขอบบน: ล้ำเข้าไปที่ {to_mm(real_y0):.1f} mm (ขอบคือ {to_mm(m_top):.1f} mm)", 
                bbox=[real_x0, real_y0, real_x1, m_top] 
            ))

    return issues