import fitz
from typing import List
from models import Issue
from utils import mm

def get_visual_areas(page: fitz.Page) -> List[fitz.Rect]:
    """
    ค้นหาพื้นที่ที่เป็น 'ตาราง' และ 'รูปภาพ' 
    โดยมีการกรองรูปภาพที่อยู่ 'ในตาราง' และ 'รูปภาพขนาดเล็ก(Noise)' ทิ้งไป
    """
    visual_rects = []
    tables_rects = [] 

    # Detect Tables
    try:
        tabs = page.find_tables()
        for tab in tabs:
            t_rect = fitz.Rect(tab.bbox)
            t_rect.x0 -= 2
            t_rect.y0 -= 2
            t_rect.x1 += 2
            t_rect.y1 += 2
            tables_rects.append(t_rect)
            visual_rects.append(t_rect)
    except Exception:
        pass

    # Detect Images
    try:
        images = page.get_images()
        for img in images:
            img_rects = page.get_image_rects(img)
            for i_rect in img_rects:
                # กรองรูปขยะ/ไอคอนเล็กๆ (น้อยกว่า 30x30 point)
                if i_rect.width < 30 or i_rect.height < 30:
                    continue
                
                # กรองรูปที่ "แฝงตัวอยู่ในตาราง"
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
    เช็คว่าจุดกึ่งกลางของข้อความ อยู่ในพื้นที่ตาราง/รูปภาพ หรือไม่
    ใช้จุดกึ่งกลางเพื่อความแม่นยำกรณี Bbox ข้อความยาวล้นเซลล์ตาราง
    """
    text_rect = fitz.Rect(bbox)
    center_pt = fitz.Point(text_rect.x0 + text_rect.width/2, 
                           text_rect.y0 + text_rect.height/2)
    
    for v_rect in visual_rects:
        if v_rect.contains(center_pt):
            return True
    return False

def check_visual_spacing(
    page_num: int, 
    page: fitz.Page, 
    visual_rects: List[fitz.Rect],
    min_gap_mm: float = 6.0 
) -> List[Issue]:
    """
    ตรวจสอบว่า 'ก่อน' ตารางหรือรูปภาพ มีการเว้นบรรทัดหรือไม่
    โดยจะไม่นำข้อความที่ 'อยู่ในตารางอื่น' มาเป็นตัวเปรียบเทียบ
    """
    issues = []
    min_gap_pt = mm(min_gap_mm) 

    text_dict = page.get_text("dict")
    blocks = text_dict.get("blocks", [])
    
    precise_text_blocks = []

    for b in blocks:
        if b.get("type") != 0: continue 
        
        # ไม่ต้องเก็บมาวัดระยะห่างกับตารางถัดไป
        if is_inside_visual(b["bbox"], visual_rects):
            continue

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

    # เรียงลำดับจากบนลงล่าง
    precise_text_blocks = sorted(precise_text_blocks, key=lambda x: x["y0"])

    for v_rect in visual_rects:
        # ข้ามตาราง/รูปที่อยู่บนสุดของหน้า

        closest_text_bottom = 0
        closest_text_top = float('inf')  
        
        found_text_above = False
        found_text_below = False        
        
        closest_text_above_bbox = None
        closest_text_below_bbox = None  
        
        for b in precise_text_blocks:
            b_y0 = b["y0"]
            b_y1 = b["y1"] 
            b_text = b["text"].strip()
                 
            # หาข้อความที่อยู่เหนือพื้นที่ Visual นี้ที่ใกล้ที่สุด
            if b_y1 < (v_rect.y0 + 5): 
                if b_y1 > closest_text_bottom:
                    closest_text_bottom = b_y1
                    closest_text_above_bbox = b["bbox"]
                    found_text_above = True

            # หาข้อความที่อยู่ใต้พื้นที่ Visual นี้ที่ใกล้ที่สุด
            if b_y0 > (v_rect.y1 - 5):
                if b_y0 < closest_text_top:
                    closest_text_top = b_y0
                    closest_text_below_bbox = b["bbox"]
                    found_text_below = True
        
        # ตรวจสอบระยะห่างด้านบน
        if found_text_above:
            gap_above = v_rect.y0 - closest_text_bottom
            if gap_above < min_gap_pt:
                severity = "error" if gap_above < -5.0 else "warning"
                gap_in_mm = gap_above * 0.352778 
                msg = f"ระยะห่างก่อนตาราง/รูปภาพน้อยเกินไป: {gap_in_mm:.1f}mm (ควรเว้น 1 บรรทัด)"
                
                issues.append(Issue(page=page_num, code="SPACING_ERR_ABOVE", severity=severity, message=msg, bbox=list(v_rect)))
                if closest_text_above_bbox:
                     issues.append(Issue(page=page_num, code="SPACING_ERR_TEXT_ABOVE", severity=severity, message=msg, bbox=list(closest_text_above_bbox)))

        # ตรวจสอบระยะห่างด้านล่าง
        if found_text_below:
            gap_below = closest_text_top - v_rect.y1
            if gap_below < min_gap_pt:
                severity = "error" if gap_below < -5.0 else "warning"
                gap_in_mm = gap_below * 0.352778 
                msg = f"ระยะห่างหลังตาราง/รูปภาพน้อยเกินไป: {gap_in_mm:.1f}mm (ควรเว้น 1 บรรทัด)"
                
                issues.append(Issue(page=page_num, code="SPACING_ERR_BELOW", severity=severity, message=msg, bbox=list(v_rect)))
                if closest_text_below_bbox:
                     issues.append(Issue(page=page_num, code="SPACING_ERR_TEXT_BELOW", severity=severity, message=msg, bbox=list(closest_text_below_bbox)))

    return issues