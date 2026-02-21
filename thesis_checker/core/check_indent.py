import re
from typing import List
from models import Issue
from utils import to_mm
from core.check_img_table import is_inside_visual 

# คัดแยกประเภทข้อความ (Classifier)
def classify_block(text: str) -> dict:
    text = text.strip()
    
    # 0. ชื่อบท (เช่น บทที่ 1, บทที่ 2)
    if re.match(r"^บทที่\s*\d+", text):
        return {"type": "CHAPTER_TITLE", "digits": 0}
        
    # 1. หัวข้อสำคัญ (เช่น 1.1)
    if re.match(r"^\d+\.\d+\s+", text):
        return {"type": "MAIN_HEADING", "digits": 1}
        
    # 2. หัวข้อรอง (เช่น 1.1.1 หรือ 1.1.10)
    match_sub = re.match(r"^\d+\.\d+\.(\d+)\s+", text)
    if match_sub:
        return {"type": "SUB_HEADING", "digits": len(match_sub.group(1))}
        
    # 3. หัวข้อย่อย (เช่น 1) หรือ 10) )
    match_list = re.match(r"^(\d+)\)\s+", text)
    if match_list:
        return {"type": "LIST_ITEM", "digits": len(match_list.group(1))}
        
    # 4. Bullet (จุดไข่ปลา)
    if text.startswith("•") or text.startswith("\u2022"):
        return {"type": "BULLET", "digits": 0}
        
    # 5. ย่อหน้าปกติ (ถ้าไม่มีตัวเลขนำหน้าเลย)
    return {"type": "PARAGRAPH", "digits": 0}

# ตรวจสอบระยะตามประเภท (Validator)
def check_page_indentation(page, page_num: int, m_left: float, rules: dict, visual_rects: list = None) -> List[Issue]:
    found_issues = []
    page_dict = page.get_text("dict")
    blocks = page_dict.get("blocks", [])
    
    if visual_rects is None: visual_rects = []
    
    # ดึงค่า Tolerance จาก Config (ถ้าไม่มีให้ใช้ 2.0)
    tolerance = rules.get("tolerance", 2.0) 
    
    for block in blocks:
        if block.get("type") != 0: continue
            
        lines = block.get("lines", [])
        if not lines: continue
            
        first_line = lines[0]
        bbox = first_line["bbox"]
        
        if is_inside_visual(bbox, visual_rects): continue
            
        spans = first_line.get("spans", [])
        if not spans: continue
        
        line_text = "".join([s["text"] for s in spans]).strip()
        if not line_text: continue
        
        dist_mm = to_mm(bbox[0] - m_left)
        
        block_info = classify_block(line_text)
        b_type = block_info["type"]
        digits = block_info["digits"]
        
        # --- ดึงเป้าหมายจาก Config ---
        target_num = None
        target_text = None
        
        if b_type == "CHAPTER_TITLE":
            target_num = None 
            
        elif b_type == "MAIN_HEADING":
            target_num = rules.get("main_heading_num", 0.0)
            target_text = rules.get("main_heading_text", 10.0)
            
        elif b_type == "SUB_HEADING":
            target_num = rules.get("sub_heading_num", 10.0)
            target_text = rules.get("sub_heading_text_1", 20.0) if digits == 1 else rules.get("sub_heading_text_2", 22.5)
            
        elif b_type == "LIST_ITEM":
            target_num = rules.get("list_item_num", 15.0)
            target_text = rules.get("list_item_text_1", 25.0) if digits == 1 else rules.get("list_item_text_2", 27.6)
            
        elif b_type == "BULLET":
            target_num = rules.get("bullet_point", 25.0)
            target_text = rules.get("bullet_text", 30.0)
            
        elif b_type == "PARAGRAPH":
            min_det = rules.get("para_min_detect", 5.0)
            max_det = rules.get("para_max_detect", 35.0)
            if min_det < dist_mm < max_det: 
                target_num = rules.get("para_indent", 10.0)
                
        # --- เริ่มตรวจสอบ ---
        if target_num is not None:
            if abs(dist_mm - target_num) > tolerance:
                msg = f"ระยะเยื้องผิด ({b_type}): เริ่มที่ {dist_mm:.1f}mm (คู่มือระบุให้เริ่มที่ {target_num}mm)"
                found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=bbox))
                
        if target_text is not None and b_type != "PARAGRAPH":
            if len(spans) > 1: 
                text_dist = to_mm(spans[1]["bbox"][0] - m_left)
                if abs(text_dist - target_text) > tolerance:
                    msg = f"ข้อความหลังเลข/จุด เริ่มผิดตำแหน่ง: เริ่มที่ {text_dist:.1f}mm (คู่มือระบุให้เริ่มที่ {target_text}mm)"
                    found_issues.append(Issue(page=page_num, code="TEXT_ALIGN_ERR", message=msg, bbox=spans[1]["bbox"]))
                    
    return found_issues