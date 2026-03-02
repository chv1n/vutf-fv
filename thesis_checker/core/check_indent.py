import re
from typing import List
from models import Issue
from utils import to_mm
from core.check_img_table import is_inside_visual 


RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RST = '\033[0m'
RST = '\033[0m'

def classify_block(text: str) -> dict:
    text = text.strip()
    
    if re.search(r"^บทท[ีี่]+", text):
        return {"type": "CHAPTER_TITLE", "digits": 0}
        
    if re.search(r"^(รูปท[ีี่]|ตารางท[ีี่]|สมการท[ีี่])", text):
        return {"type": "CAPTION", "digits": 0}
        
    if re.match(r"^\d+\.\d+\s+", text):
        print(f"{RED}ตรวจพบ Main Heading: '{text}'{RST}")
        return {"type": "MAIN_HEADING", "digits": 1}
        
    match_sub = re.match(r"^\d+\.\d+\.(\d+)\s+", text)
    if match_sub:
        print(f"{RED}ตรวจพบ Sub Heading: '{text}' (digits: {match_sub.group(1)}){RST}")
        return {"type": "SUB_HEADING", "digits": len(match_sub.group(1))}
        
    match_list = re.match(r"^([ก-ฮa-zA-Z0-9]+)\s*\)\s*", text)
    if match_list:
        print(f"{RED}ตรวจพบ List Item: '{text}' (digits: {match_list.group(1)}){RST}")
        return {"type": "LIST_ITEM", "digits": len(match_list.group(1))}
        
    if text.startswith("•") or text.startswith("\u2022"):
        print(f"{RED}ตรวจพบ Bullet Point: '{text}'{RST}")
        return {"type": "BULLET", "digits": 0}

    if _is_formula(text):
        return {"type": "FORMULA", "digits": 0}
        
    return {"type": "PARAGRAPH", "digits": 0}

def _is_formula(text: str) -> bool:
    """ตรวจว่าข้อความเป็นสูตร/สมการหรือไม่"""
    if '=' in text and len(text) < 200:
        thai_chars = len(re.findall(r'[\u0E00-\u0E7F]', text))
        total_chars = len(text.replace(' ', ''))
        if total_chars > 0 and (thai_chars / total_chars) < 0.3:
            return True
    
    math_symbols = set('×÷±≤≥≠∑∫√∆∞αβγδεζηθλμπσφωΩ')
    if any(c in math_symbols for c in text):
        return True
    
    if len(text) < 100:
        math_ops = len(re.findall(r'[+\-*/=<>^²³]', text))
        if math_ops >= 2:
            thai_chars = len(re.findall(r'[\u0E00-\u0E7F]', text))
            if thai_chars < 3:
                return True
    
    return False

def check_page_indentation(page, page_num: int, m_left: float, rules: dict, visual_rects: list = None) -> List[Issue]:
    found_issues = []
    page_dict = page.get_text("dict")
    blocks = page_dict.get("blocks", [])
    
    if visual_rects is None: visual_rects = []
    
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
        
        target_num = None
        target_text = None
        
        # รวมกลุ่มที่ "ไม่ต้องตรวจ Indent ขอบซ้าย" ไว้ด้วยกัน
        if b_type in ["CHAPTER_TITLE", "CAPTION"]:
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
            # เช็คว่า indent ตรงกับ text indent ของหัวข้อระดับใดหรือไม่
            # ถ้าตรง → เป็นข้อความต่อเนื่องของหัวข้อ (continuation line) → ข้ามไม่ตรวจ
            known_text_indents = [
                rules.get("main_heading_text", 10.0),
                rules.get("sub_heading_text_1", 20.0),
                rules.get("sub_heading_text_2", 22.5),
                rules.get("list_item_text_1", 25.0),
                rules.get("list_item_text_2", 27.6),
                rules.get("bullet_text", 30.0),
            ]
            is_continuation = any(abs(dist_mm - t) <= tolerance for t in known_text_indents)
            
            if not is_continuation:
                min_det = rules.get("para_min_detect", 5.0)
                max_det = rules.get("para_max_detect", 35.0)
                if min_det < dist_mm < max_det: 
                    target_num = rules.get("para_indent", 10.0)
                
        # เริ่มตรวจสอบ
        if target_num is not None:
            if abs(dist_mm - target_num) > tolerance:
                msg = f"ระยะเยื้องผิด ({b_type}): เริ่มที่ {dist_mm:.1f}mm (คู่มือระบุให้เริ่มที่ {target_num}mm)"
                found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=bbox))
                
        if target_text is not None and b_type != "PARAGRAPH":
            
            # skip " "
            target_text_span = None
            for i in range(1, len(spans)):
                if spans[i]["text"].strip():
                    target_text_span = spans[i]
                    break
                    
            if target_text_span: 
                text_dist = to_mm(target_text_span["bbox"][0] - m_left)
                if abs(text_dist - target_text) > tolerance:
                    msg = f"ข้อความหลังเลข/จุด เริ่มผิดตำแหน่ง: เริ่มที่ {text_dist:.1f}mm (คู่มือระบุให้เริ่มที่ {target_text}mm)"
                    found_issues.append(Issue(page=page_num, code="TEXT_ALIGN_ERR", message=msg, bbox=target_text_span["bbox"]))
                    
    return found_issues