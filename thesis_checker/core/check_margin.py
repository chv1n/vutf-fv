from typing import List, Dict, Any
from models import Issue
from utils import mm

def check_margin_rules(
    page_num: int, 
    page_elements: List[Dict[str, Any]], 
    margin_cfg: dict, 
    page_width: float, 
    page_height: float
) -> List[Issue]:
    """
    ตรวจสอบระยะขอบแบบ 'ทีละบรรทัด/ทีละก้อน (Line-by-Line)'
    เพื่อแยกแยะว่าบรรทัดไหนล้นจริงๆ และหลบปัญหา Space ล่องหนท้ายบรรทัด
    """
    issues = []
    
    m_top = mm(margin_cfg.get("top", 25.4))
    m_bottom = mm(margin_cfg.get("bottom", 25.4))
    m_left = mm(margin_cfg.get("left", 38.1))
    m_right = mm(margin_cfg.get("right", 25.4))
    
    TOLERANCE = 3.0 
    limit_right = page_width - m_right
    limit_bottom = page_height - m_bottom

    for element in page_elements:
        bbox = element.get("bbox")
        spans = element.get("spans", [])
        
        if not bbox:
            continue
            
        real_x0, real_y0, real_x1, real_y1 = bbox
        
        has_text = False
        ends_with_space = False 
        
        if spans:
            valid_left_edges = []
            valid_right_edges = []
            valid_top_edges = []
            valid_bottom_edges = []
            
            last_valid_text = ""
            
            for span in spans:
                text = span.get("text", "")
                if not text.strip(): 
                    continue
                
                has_text = True
                last_valid_text = text 
                
                span_bbox = span.get("bbox")
                if span_bbox:
                    valid_left_edges.append(span_bbox[0])
                    valid_right_edges.append(span_bbox[2])
                    valid_top_edges.append(span_bbox[1])
                    valid_bottom_edges.append(span_bbox[3])
            
            if has_text:
                real_x0 = min(valid_left_edges)
                real_x1 = max(valid_right_edges)
                real_y0 = min(valid_top_edges)
                real_y1 = max(valid_bottom_edges)
                
                if last_valid_text.endswith(" ") or last_valid_text.endswith("\u00A0"):
                    ends_with_space = True
                    
        if not has_text:
            continue
        
        current_right_tolerance = TOLERANCE + 6.0 if ends_with_space else TOLERANCE

        if real_x0 < (m_left - TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_LEFT", severity="error", 
                message=f"เนื้อหาล้นขอบซ้าย: ล้ำเข้าไปที่ {real_x0:.1f} pt (ขอบอยู่ที่ {m_left:.1f} pt)", 
                bbox=[real_x0, real_y0, m_left, real_y1] 
            ))

        if real_x1 > (limit_right + current_right_tolerance):
            issues.append(Issue(
                page=page_num, code="MARGIN_RIGHT", severity="error", 
                message=f"เนื้อหาล้นขอบขวา: ล้ำไปที่ {real_x1:.1f} pt (เกินมา {real_x1 - limit_right:.1f} pt)", 
                bbox=[limit_right, real_y0, real_x1, real_y1] 
            ))

        if real_y0 < (m_top - TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_TOP", severity="error", 
                message=f"เนื้อหาล้นขอบบน: ล้ำเข้าไปที่ {real_y0:.1f} pt (ขอบอยู่ที่ {m_top:.1f} pt)", 
                bbox=[real_x0, real_y0, real_x1, m_top] 
            ))

        if real_y1 > (limit_bottom + TOLERANCE):
            issues.append(Issue(
                page=page_num, code="MARGIN_BOTTOM", severity="error", 
                message=f"เนื้อหาล้นขอบล่าง: ล้ำไปที่ {real_y1:.1f} pt (เกินมา {real_y1 - limit_bottom:.1f} pt)", 
                bbox=[real_x0, limit_bottom, real_x1, real_y1] 
            ))

    return issues