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
    
    target_top = margin_cfg.get("top", 25.4)
    target_bottom = margin_cfg.get("bottom", 25.4)
    target_left = margin_cfg.get("left", 38.1)
    target_right = margin_cfg.get("right", 25.4)
    
    TOLERANCE = 2.0

    for element in page_elements:
        all_chars = []
        for span in element.get("spans", []):
            if "chars" in span: all_chars.extend(span["chars"])

        if not all_chars: continue

        non_space_indices = [i for i, char in enumerate(all_chars) if char.get("c", "").strip()]
        if not non_space_indices: continue

        real_rect = fitz.Rect()
        for i in range(non_space_indices[0], non_space_indices[-1] + 1):
            real_rect.include_rect(all_chars[i]["bbox"])

        curr_x0 = to_mm(real_rect.x0)
        curr_y0 = to_mm(real_rect.y0)
        curr_x1 = to_mm(real_rect.x1)
        curr_y1 = to_mm(real_rect.y1)
        
        # แปลงขนาดหน้ากระดาษเป็น mm เพื่อหาขอบขวา/ล่าง
        page_w_mm = to_mm(page_width)
        page_h_mm = to_mm(page_height)

        # ตรวจขอบซ้าย
        if curr_x0 < (target_left - TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_LEFT", severity="error", 
                message=f"เนื้อหาล้นขอบซ้าย: อยู่ที่ {curr_x0:.1f} mm (ขอบคือ {target_left:.1f} mm)", 
                bbox=list(real_rect) 
            ))

        # ตรวจขอบขวา
        limit_right = page_w_mm - target_right
        if curr_x1 > (limit_right + TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_RIGHT", severity="error", 
                message=f"เนื้อหาล้นขอบขวา: อยู่ที่ {curr_x1:.1f} mm (ขอบคือ {limit_right:.1f} mm)", 
                bbox=list(real_rect)
            ))

        # ตรวจขอบบน
        if curr_y0 < (target_top - TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_TOP", severity="error", 
                message=f"เนื้อหาล้นขอบบน: อยู่ที่ {curr_y0:.1f} mm (ขอบคือ {target_top:.1f} mm)", 
                bbox=list(real_rect)
            ))

        # ตรวจขอบล่าง
        limit_bottom = page_h_mm - target_bottom
        if curr_y1 > (limit_bottom + TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_BOTTOM", severity="error", 
                message=f"เนื้อหาล้นขอบล่าง: อยู่ที่ {curr_y1:.1f} mm (ขอบคือ {limit_bottom:.1f} mm)", 
                bbox=list(real_rect)
            ))

    return issues