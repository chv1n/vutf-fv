from typing import List
from models import Issue
from utils import mm

def check_margin_rules(
    page_num: int, 
    bbox: list, 
    margin_cfg: dict, 
    page_width: float, 
    page_height: float,
    spans: list = None
) -> List[Issue]:
    """
    ตรวจสอบระยะขอบ โดยตัดพื้นที่ว่าง (Whitespace) ท้ายบรรทัดออกก่อนคำนวณ
    """
    issues = []
    
    m_top = mm(margin_cfg.get("top", 25.4))
    m_bottom = mm(margin_cfg.get("bottom", 25.4))
    m_left = mm(margin_cfg.get("left", 38.1))
    m_right = mm(margin_cfg.get("right", 25.4))
    
    TOLERANCE = 3.0

    # ค่า Default คือเชื่อ bbox เดิมไปก่อน
    x0, y0, x1, y1 = bbox
    
    # คำนวณขอบเขตจริง (Real Content Boundary)
    real_x1 = x1
    
    if spans:
        valid_right_edges = []
        for span in spans:
            text = span["text"]
            # ถ้าเป็นช่องว่างล้วนๆ หรือตัวอักษรที่มองไม่เห็น ให้ข้ามไป
            if not text.strip():
                continue
            
            # เก็บค่าขอบขวาของ span ที่มีตัวหนังสือจริง
            valid_right_edges.append(span["bbox"][2])
        
        # ถ้ามี span ที่ใช้งานได้ ให้เอาค่าที่ขวาสุดมาเป็นขอบเขตจริง
        if valid_right_edges:
            real_x1 = max(valid_right_edges)
        else:
            # ถ้าทั้งบรรทัดมีแต่ช่องว่าง (บรรทัดเปล่า) ให้ถือว่าไม่ล้น
            real_x1 = 0 


    if x0 < (m_left - TOLERANCE):
        issues.append(Issue(
            page=page_num, code="MARGIN_LEFT", severity="error", 
            message=f"ล้นขอบซ้าย: {x0:.1f} pt", bbox=bbox
        ))

    # limit_right = page_width - m_right
    
    # # ใช้ real_x1 เทียบกับขอบกระดาษ
    # if real_x1 > (limit_right + TOLERANCE):
    #     issues.append(Issue(
    #         page=page_num, code="MARGIN_RIGHT", severity="error", 
    #         message=f"ล้นขอบขวา: {real_x1:.1f} pt (เกินมา {real_x1 - limit_right:.1f})", 
    #         bbox=bbox
    #     ))

    if y0 < (m_top - TOLERANCE):
        issues.append(Issue(
            page=page_num, code="MARGIN_TOP", severity="error", 
            message=f"ล้นขอบบน: {y0:.1f} pt", bbox=bbox
        ))

    # limit_bottom = page_height - m_bottom
    # if y1 > (limit_bottom + TOLERANCE):
    #     issues.append(Issue(
    #         page=page_num, code="MARGIN_BOTTOM", severity="error", 
    #         message=f"ล้นขอบล่าง: {y1:.1f} pt", bbox=bbox
    #     ))

    return issues