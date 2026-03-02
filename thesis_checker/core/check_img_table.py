import fitz
from typing import List, Tuple
from models import Issue
from utils import mm

def get_visual_areas(page: fitz.Page) -> List[fitz.Rect]:
    """
    ค้นหาพื้นที่ที่เป็น 'ตาราง' และ 'รูปภาพ' 
    โดยมีการกรองรูปภาพที่อยู่ 'ในตาราง' และ 'รูปภาพขนาดเล็ก(Noise)' ทิ้งไป
    """
    visual_rects = []
    tables_rects = []

    try:
        tables = page.find_tables()
        for tab in tables:
            t_rect = fitz.Rect(tab.bbox)
            tables_rects.append(t_rect)
            visual_rects.append(t_rect)
    except Exception:
        pass

    try:
        images = page.get_images()
        for img in images:
            img_rects = page.get_image_rects(img)
            for i_rect in img_rects:
                
                if i_rect.width < 30 or i_rect.height < 30:
                    continue
                
                is_inside_table = False
                for t_rect in tables_rects:
                    intersect = i_rect & t_rect
                    if not intersect.is_empty and intersect.get_area() > (i_rect.get_area() * 0.5):
                        is_inside_table = True
                        break
                
                if not is_inside_table:
                    visual_rects.append(i_rect)
    except Exception:
        pass

    return visual_rects

def is_inside_visual(bbox: list, visual_rects: List[fitz.Rect]) -> bool:
    """
    เช็คว่า bbox ของข้อความ อยู่ในพื้นที่ตาราง/รูปภาพ หรือไม่
    (ถ้าอยู่ -> True เพื่อให้ Main Loop ข้ามการตรวจ Indent/Font)
    """
    text_rect = fitz.Rect(bbox)
    
    for v_rect in visual_rects:
        intersect = text_rect & v_rect 
        if intersect.is_empty:
            continue
            
        if intersect.get_area() > (text_rect.get_area() * 0.5):
            return True
            
    return False

def check_visual_spacing(
    page_num: int, 
    page: fitz.Page, 
    visual_rects: List[fitz.Rect],
    min_gap_mm: float = 4.0
) -> List[Issue]:
    """
    ตรวจสอบว่า 'ก่อน' ตารางหรือรูปภาพ มีการเว้นบรรทัดหรือไม่
    โดยตัดกรอบล่องหนที่เกิดจากการเคาะ Enter (Empty Lines) ทิ้งไปก่อนคำนวณ
    """
    issues = []
    min_gap_pt = mm(min_gap_mm) 

    text_dict = page.get_text("dict")
    blocks = text_dict.get("blocks", [])
    
    precise_text_blocks = []

    for b in blocks:
        if b.get("type") != 0: continue 
        
        lines = b.get("lines", [])
        valid_lines = []
        
        for line in lines:
            spans = line.get("spans", [])
            line_text = "".join(s.get("text", "") for s in spans).strip()
            
            if line_text:
                valid_lines.append({
                    "bbox": line["bbox"],
                    "text": line_text
                })
        
        if valid_lines:
            true_y0 = valid_lines[0]["bbox"][1]
            true_y1 = valid_lines[-1]["bbox"][3]
            full_text = "\n".join(l["text"] for l in valid_lines)
            
            b_bbox = b["bbox"]
            precise_bbox = fitz.Rect(b_bbox[0], true_y0, b_bbox[2], true_y1)
            
            precise_text_blocks.append({
                "y0": true_y0,
                "y1": true_y1,
                "text": full_text,
                "bbox": precise_bbox
            })

    precise_text_blocks = sorted(precise_text_blocks, key=lambda x: x["y0"])

    for v_rect in visual_rects:
        if v_rect.y0 < 100: 
            continue

        closest_text_bottom = 0
        found_text_above = False
        closest_text_bbox = None
        
        for b in precise_text_blocks:
            b_y1 = b["y1"] 
            b_text = b["text"].strip()
            
            if b_text.startswith("รูปที่") or b_text.startswith("ตารางที่"):
                 continue 
                 
            if b_y1 < (v_rect.y0 + 5): 
                if b_y1 > closest_text_bottom:
                    closest_text_bottom = b_y1
                    closest_text_bbox = b["bbox"]
                    found_text_above = True
        
        if found_text_above:
            gap = v_rect.y0 - closest_text_bottom
            
            if gap < min_gap_pt:
                severity = "error" if gap < -5.0 else "warning"
                gap_in_mm = gap * 0.352778 
                msg = f"ระยะห่างก่อนตาราง/รูปภาพน้อยเกินไป: ห่างเพียง {gap_in_mm:.1f}mm (ควรเว้น 1 บรรทัด)"
                
                issues.append(Issue(
                    page=page_num,
                    code="SPACING_ERR",
                    severity=severity,
                    message=msg,
                    bbox=[v_rect.x0, v_rect.y0, v_rect.x1, v_rect.y1]
                ))
                
                if closest_text_bbox is not None and not closest_text_bbox.is_empty:
                     issues.append(Issue(
                        page=page_num,
                        code="SPACING_ERR_TEXT",
                        severity=severity,
                        message=msg,
                        bbox=[closest_text_bbox.x0, closest_text_bbox.y0, closest_text_bbox.x1, closest_text_bbox.y1]
                    ))

    return issues