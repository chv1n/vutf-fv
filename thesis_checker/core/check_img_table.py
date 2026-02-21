import fitz
from typing import List, Tuple
from models import Issue
from utils import mm

def get_visual_areas(page: fitz.Page) -> List[fitz.Rect]:
    """
    ค้นหาพื้นที่ที่เป็น 'ตาราง' และ 'รูปภาพ' ทั้งหมดในหน้า
    คืนค่าเป็น List ของ Rect เพื่อเอาไปใช้เช็ค exclusion
    """
    visual_rects = []

    # 1. Detect Tables (ใช้ built-in ของ pymupdf)
    try:
        tables = page.find_tables()
        for tab in tables:
            visual_rects.append(fitz.Rect(tab.bbox))
    except Exception:
        pass # กันเหนียวเผื่อหาไม่เจอ

    # 2. Detect Images
    try:
        images = page.get_images()
        for img in images:
            # รูปหนึ่งรูปอาจมีหลายตำแหน่ง (rects)
            img_rects = page.get_image_rects(img)
            visual_rects.extend(img_rects)
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
        # ใช้ intersects แทน contains เผื่อข้อความล้นกรอบนิดหน่อยก็ให้นับรวม
        # หรือถ้าเอาเป๊ะๆ ใช้: if v_rect.contains(text_rect):
        
        # คำนวณพื้นที่ทับซ้อน (Intersection)
        intersect = text_rect & v_rect 
        if intersect.is_empty:
            continue
            
        # ถ้าพื้นที่ทับซ้อนเกิน 50% ของข้อความ ให้ถือว่าอยู่ในตาราง/รูป
        if intersect.get_area() > (text_rect.get_area() * 0.5):
            return True
            
    return False

def check_visual_spacing(
    page_num: int, 
    page: fitz.Page, 
    visual_rects: List[fitz.Rect],
    min_gap_mm: float = 6.0 # ค่า Default: ~1 บรรทัดเปล่า (16pt font + leading ~ 22pt -> 7-8mm)
) -> List[Issue]:
    """
    ตรวจสอบว่า 'ก่อน' ตารางหรือรูปภาพ มีการเว้นบรรทัดหรือไม่
    """
    issues = []
    
    # ดึงข้อความทั้งหมดมาเพื่อหาว่า "บรรทัดล่าสุดก่อนเจอรูป" อยู่ตรงไหน
    text_blocks = page.get_text("blocks")
    # block format: (x0, y0, x1, y1, "text", block_no, block_type)
    
    # กรองเฉพาะ Text Block (type=0) และเรียงตามแกน Y
    text_blocks = sorted([b for b in text_blocks if b[6] == 0], key=lambda x: x[1])

    min_gap_pt = mm(min_gap_mm) # แปลง config เป็น point

    for v_rect in visual_rects:
        # ข้ามถ้า object อยู่บนสุดของหน้า (y0 น้อยๆ) เพราะขึ้นหน้าใหม่ไม่ต้องเว้นก็ได้
        if v_rect.y0 < 100: 
            continue

        # หา Text Block ที่อยู่ "เหนือ" object นี้ และใกล้ที่สุด
        closest_text_bottom = 0
        found_text_above = False
        
        for b in text_blocks:
            b_y1 = b[3] # ขอบล่างของ text
            # ถ้า text อยู่เหนือ object
            if b_y1 < v_rect.y0:
                if b_y1 > closest_text_bottom:
                    closest_text_bottom = b_y1
                    found_text_above = True
        
        if found_text_above:
            gap = v_rect.y0 - closest_text_bottom
            
            # ถ้าช่องว่างน้อยกว่าค่าที่กำหนด (แปลว่าไม่ได้เคาะ Enter 1 ที)
            if gap < min_gap_pt:
                issues.append(Issue(
                    page=page_num,
                    code="SPACING_ERR",
                    severity="warning", # หรือ error
                    message=f"ระยะห่างก่อนตาราง/รูปภาพน้อยไป: {gap:.1f}pt (ควรเว้น 1 บรรทัด)",
                    bbox=v_rect
                ))

    return issues