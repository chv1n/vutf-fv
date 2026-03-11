import re 
import fitz
from typing import List
from models import Issue, ThesisState
from utils import pt_to_mm
from core.check_utils import is_bold, is_formula, get_prefix_and_text_coords
from core.check_img_table import is_inside_visual 

# ตรวจสอบระยะตามประเภท รับข้อมูลมาทั้ง Page
def check_page_indentation(state: ThesisState, page, page_num: int, m_left: float, rules: dict, visual_rects: list = None, ignored_units: list = None, page_num_rect=None) -> List[Issue]:
    found_issues = []

    if visual_rects is None: 
        visual_rects = []
    tolerance = rules.get("tolerance", 2.0)

    # ดึงข้อมูลแบบ rawdict
    page_dict = page.get_text("rawdict")
    blocks = page_dict.get("blocks", [])
    
    # กรองและเรียงบรรทัดจากบนลงล่าง
    all_lines = []
    for block in blocks:
        if block.get("type") != 0: continue
        for line in block.get("lines", []):
            all_lines.append(line)
    all_lines.sort(key=lambda l: l["bbox"][1])

    # ดึง State จากหน้าก่อน
    prev_text = state.prev_line_text 
    prev_line_type = "paragraph"
    prev_line_x1 = state.prev_line_x1
    prev_dist_mm = getattr(state, "prev_dist_mm", 0.0) # ดึงค่าระยะเยื้องบรรทัดที่แล้ว

    for line in all_lines:
        l_bbox = fitz.Rect(line["bbox"])
        line_text = "".join([c["c"] for s in line["spans"] for c in s["chars"]]).strip()
        if not line_text: 
            continue

        # กรองโซนเลขหน้า
        if page_num_rect and l_bbox.intersects(page_num_rect):
            continue

        # ถ้าอยู่ใน Visual Area (รูป/ตาราง) ไม่ต้องตรวจ
        if is_inside_visual(line["bbox"], visual_rects): 
            continue

        result = get_prefix_and_text_coords(line)
        line_type = result["type"]
        prefix_str = result["prefix"]
        digits = result.get("digits", 0)
        prefix_x0 = result["prefix_x0"]
        text_x0 = result["text_x0"]

        # กฎปลดยศหัวข้อปลอม (Downgrade)
        if line_type in ["section", "sub_section", "sub_sub_section"]:
            if prev_text.strip().endswith(("รูปที่", "ตารางที่", "สมการที่", "และ", "จาก", "ใน", "ของ", "คือ", "ได้แก่", "ดังนี้", "ว่า")):
                line_type = "paragraph" # กลายเป็นย่อหน้าธรรมดา
                prefix_str = ""         # ล้างค่า Prefix ทิ้ง เพื่อไม่ให้เอาไปคำนวณระยะผิดๆ

        # กรอง Ghost Heading (มีแต่เลข ไม่มีเนื้อหา)
        if prefix_str and line_text == prefix_str:
            continue
    
        dist_mm = pt_to_mm(prefix_x0 - m_left)

        # กรองค่าวัดที่มี Unit นำหน้า
        if ignored_units and prefix_str and line_type == "section":
            suffix_text = line_text.replace(prefix_str, "", 1).strip()
            if any(suffix_text.startswith(u) or suffix_text == u for u in ignored_units):
                prev_text = line_text
                continue
        
        target_num = None
        target_text = None

        # กำหนดเป้าหมาย ตามประเภทบรรทัด
        if line_type == "section":
            target_num = rules.get("main_heading_num", 0.0)
            target_text = rules.get("main_heading_text", 10.0)
            if not is_bold(line):
                found_issues.append(Issue(page=page_num, code="FONT_STYLE_ERR", message=f"หัวข้อสำคัญ ({prefix_str}) ต้องเป็นตัวหนา", bbox=line["bbox"]))

        elif line_type == "sub_section":
            target_num = rules.get("sub_heading_num", 10.0)
            try:
                parts = prefix_str.split(".")
                mid_digits  = len(parts[1]) if len(parts) > 1 else 1
                last_digits = len(parts[2]) if len(parts) > 2 else 1
            except (IndexError, AttributeError):
                mid_digits, last_digits = 1, 1

            if mid_digits >= 2 and last_digits >= 2: target_text = rules.get("sub_heading_text_3", 24.5)
            elif mid_digits >= 2 or last_digits >= 2: target_text = rules.get("sub_heading_text_2", 22.5)
            else: target_text = rules.get("sub_heading_text_1", 20.0)
            
        elif line_type == "sub_sub_section":
            target_num = state.last_heading_text_indent
            target_text = rules.get("list_item_text_1", 25.0) if digits == 1 else rules.get("list_item_text_2", 27.6)
            
        elif line_type == "bullet":
            target_num = rules.get("bullet_point", 25.0)
            target_text = rules.get("bullet_text", 30.0)

        elif line_type == "dash":
            target_num = rules.get("dash_indent", 30.0)
            target_text = rules.get("dash_text", 35.0) 

        # ตรวจสอบ Error (แยก Paragraph กับ พวกที่มี Target)
        if line_type == "paragraph":
            para_min = rules.get("para_min_detect", 5.0)
            para_max = rules.get("para_max_detect", 35.0)

            known_text_indents = [
                rules.get("main_heading_text", 10.0), rules.get("sub_heading_text_1", 20.0),
                rules.get("sub_heading_text_2", 22.5), rules.get("sub_heading_text_3", 24.5),
                rules.get("list_item_text_1", 25.0), rules.get("list_item_text_2", 27.6),
                rules.get("bullet_text", 30.0),
            ]

            last_indent = state.last_heading_text_indent if state.last_heading_text_indent else 10.0
            prev_line_x1_mm = pt_to_mm(prev_line_x1)
            short_line_max = rules.get("short_line_max", 120.0)
            full_line_min = rules.get("full_line_min", 145.0)

            if prev_line_x1_mm < short_line_max:
                expected_indent = last_indent
            elif prev_line_x1_mm > full_line_min:
                expected_indent = 0.0
            else:
                if dist_mm >= para_min: expected_indent = last_indent
                else: expected_indent = 0.0

            # paragraph ที่ต่อจากลิสต์ (1, 2, bullet) ถ้าชิดซ้ายให้อนุโลม
            if prev_line_type in ["sub_sub_section", "bullet", "dash"] and dist_mm < para_min:
                expected_indent = 0.0

            # ป้องกัน Word Wrap ในบรรทัดแรกของย่อหน้า
            if prev_line_type == "paragraph" and prev_dist_mm >= para_min and dist_mm < para_min:
                expected_indent = 0.0

            is_known_continuation = any(abs(dist_mm - t) <= tolerance for t in known_text_indents)

            if not is_known_continuation:
                if para_min <= dist_mm <= para_max:
                    if abs(dist_mm - expected_indent) > tolerance:
                        msg = f"ระยะเยื้องผิด ({line_type}): เริ่มที่ {dist_mm:.1f}mm (เป้าหมาย {expected_indent}mm)"
                        found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=line["bbox"]))
                
                elif dist_mm < para_min:
                    if expected_indent > 0.0:
                        msg = f"ลืมเว้นย่อหน้า: ต้องเยื้อง {expected_indent}mm แต่พบว่าชิดขอบซ้าย ({dist_mm:.1f}mm)"
                        found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=line["bbox"]))
                    
                    elif expected_indent == 0.0 and dist_mm > tolerance:
                        msg = f"บรรทัดนี้ต้องชิดขอบซ้าย: เริ่มที่ {dist_mm:.1f}mm (เป้าหมาย 0.0mm)"
                        found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=line["bbox"]))

        else:
            # เช็คระยะของ "ตัวเลข/สัญลักษณ์"
            if target_num is not None and abs(dist_mm - target_num) > tolerance:
                msg = f"ระยะเยื้องตัวเลขผิด ({line_type}): เริ่มที่ {dist_mm:.1f}mm (เป้าหมาย {target_num}mm)"
                found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=line["bbox"]))

            # เช็คระยะของ "ข้อความ" (หลังตัวเลข)
            if target_text is not None and text_x0 is not None:
                text_dist_mm = pt_to_mm(text_x0 - m_left) # แปลงค่าเป็น mm ก่อน
                if abs(text_dist_mm - target_text) > tolerance:
                    msg = f"ระยะเยื้องข้อความผิด ({line_type}): เริ่มที่ {text_dist_mm:.1f}mm (เป้าหมาย {target_text}mm)"
                    found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=line["bbox"]))

        # อัปเดต State บรรทัดต่อบรรทัด
        prev_text = line_text 
        prev_line_type = line_type
        prev_line_x1 = l_bbox.x1
        prev_dist_mm = dist_mm # บันทึกระยะเยื้องของบรรทัดนี้ลง local state

    # อัปเดตกลับไปที่ global State เพื่อส่งต่อให้หน้าถัดไป
    state.prev_line_x1 = prev_line_x1
    state.prev_line_text = prev_text
    state.prev_dist_mm = prev_dist_mm # global State
    
    return found_issues