import re 
import fitz
from typing import List
from models import Issue
from utils import to_mm
from core.check_utils import is_bold, get_prefix_and_text_coords
from core.check_img_table import is_inside_visual 
from models import ThesisState

# ตรวจสอบระยะตามประเภท
def check_page_indentation(state: ThesisState, page, page_num: int, m_left: float, rules: dict, visual_rects: list = None, ignored_units: list = None) -> List[Issue]:
    found_issues = []

    # ดึงข้อมูลแบบ rawdict
    page_dict = page.get_text("rawdict")
    blocks = page_dict.get("blocks", [])
    
    if visual_rects is None: 
        visual_rects = []
    tolerance = rules.get("tolerance", 2.0)
    
    # กรองและเรียงบรรทัดจากบนลงล่าง
    all_lines = []
    for block in blocks:
        if block.get("type") != 0: continue
        for line in block.get("lines", []):
            all_lines.append(line)
    all_lines.sort(key=lambda l: l["bbox"][1])

    prev_text = state.prev_line_text
    prev_b_type = "paragraph"        
    prev_l_bbox = None  # <--- [เพิ่มบรรทัดนี้] สร้างตัวแปรเก็บพิกัดบรรทัดก่อนหน้า
    active_caption_indent = None  # <--- [เพิ่มบรรทัดนี้] สร้างตัวแปรเก็บระยะเยื้องของชื่อรูป/ตาราง

    for line in all_lines:

        line_text = "".join([c["c"] for s in line["spans"] for c in s["chars"]]).strip()
        if not line_text: 
            continue

        result = get_prefix_and_text_coords(line)
        
        b_type = result["type"]
        prefix_str = result["prefix"]
        digits = result.get("digits", 0)
        prefix_x0 = result["prefix_x0"]
        text_x0 = result["text_x0"]

        # ถ้า prefix_str มีค่า แต่ line_text ดันเท่ากับ prefix_str พอดี แสดงว่าบรรทัดนั้นมีแต่เลขหัวข้อ ไม่มีเนื้อหา
        # กรณีนี้ให้ข้ามไปเลย ไม่ต้องตรวจ
        if prefix_str and line_text == prefix_str:
            continue
    
        dist_mm = to_mm(prefix_x0 - m_left)

        # if b_type == "paragraph" and dist_mm > 30.0: 
        #     continue
        
        # --- [ตะแกรงร่อนหัวข้อปลอม V5] ---
        text_dist_mm = to_mm(text_x0 - m_left) if text_x0 is not None else dist_mm
        is_fake = False
        l_bbox = fitz.Rect(line["bbox"])
        
        gap_y0 = (l_bbox.y0 - prev_l_bbox.y0) if prev_l_bbox else 100.0
        is_continuous = gap_y0 < 35.0  
        
        if b_type == "section":
            if is_continuous and text_dist_mm < 8.0:
                is_fake = True
            elif dist_mm > 15.0:
                is_fake = True
                
        elif b_type == "sub_section":
            if is_continuous and dist_mm < 5.0:
                is_fake = True
            elif dist_mm > 20.0:
                is_fake = True

        if is_fake:
            b_type = "paragraph"
            prefix_str = ""
        # -----------------------------------------------
        
        # ถ้าอยู่ใน Visual Area ไม่ต้องตรวจ
        if is_inside_visual(line["bbox"], visual_rects): 
            continue

        # --- [อัปเกรด V2: ตรวจระยะบรรทัด 2 ของชื่อรูป/ตาราง + ดักการลืมเว้นบรรทัด] ---
        if prev_text.startswith("รูปที่") or prev_text.startswith("ตารางที่"):
            gap_y0 = (l_bbox.y0 - prev_l_bbox.y0) if prev_l_bbox else 100.0
            
            if gap_y0 < 35.0: # บรรทัดติดกัน (ไม่ได้เว้นบรรทัด)
                
                # เช็คว่าบรรทัดที่แล้วพิมพ์จนชนขอบขวาไหม (เช็คการ Wrap text)
                limit_x1_pt = page.rect.width - 120.0
                is_prev_full = prev_l_bbox.x1 > limit_x1_pt

                if is_prev_full:
                    # กรณีที่ 1: ชนขอบขวา -> เป็นบรรทัดที่ 2 ของชื่อรูป/ตารางจริงๆ
                    if active_caption_indent is not None:
                        if abs(dist_mm - active_caption_indent) > tolerance:
                            msg = f"บรรทัดต่อมาของชื่อรูป/ตารางผิดตำแหน่ง: เริ่มที่ {dist_mm:.1f}mm (เป้าหมาย {active_caption_indent:.1f}mm)"
                            found_issues.append(Issue(page=page_num, code="CAPTION_ALIGN_ERR", message=msg, bbox=line["bbox"]))
                    
                    prev_text = "รูปที่" if prev_text.startswith("รูปที่") else "ตารางที่"
                    prev_b_type = b_type
                    prev_l_bbox = l_bbox 
                    continue
                else:
                    # กรณีที่ 2: ไม่ชนขอบขวา -> จบชื่อรูปแล้ว แต่นักศึกษา "ลืมเว้นบรรทัด" ก่อนขึ้นย่อหน้าใหม่!
                    found_issues.append(Issue(
                        page=page_num, 
                        code="SPACING_ERR", 
                        message="รูปแบบผิด: ต้องเว้นว่าง 1 บรรทัด หลังชื่อรูปภาพหรือตาราง", 
                        bbox=line["bbox"]
                    ))
                    
                    # === ดึงความจำจากสมองก้อนใหม่ (last_text_target) ===
                    expected_indent = getattr(state, "last_text_target", 10.0)
                    
                    if abs(dist_mm - expected_indent) > tolerance:
                        msg = f"ระยะเยื้องผิด (paragraph): เริ่มที่ {dist_mm:.1f}mm (เป้าหมาย {expected_indent:.1f}mm)"
                        
                        # --- [เพิ่มส่วนนี้] สร้างกรอบเล็กเฉพาะ "ช่องว่างที่ผิด" ---
                        actual_x0 = l_bbox.x0
                        target_x0 = m_left + (expected_indent * 2.83465) # แปลงเป้าหมาย (mm) กลับเป็นจุด (pt)
                        
                        box_x0 = min(actual_x0, target_x0)
                        box_x1 = max(actual_x0, target_x0)
                        # ถ้าจุดที่พิมพ์กับเป้าหมายอยู่ใกล้กันมาก (กรอบจะบางไป) ให้บังคับกว้างอย่างน้อย 10pt
                        if box_x1 - box_x0 < 10.0: box_x1 = box_x0 + 10.0 
                        
                        custom_bbox = [box_x0, l_bbox.y0, box_x1, l_bbox.y1]
                        # ------------------------------------------------
                        
                        # สังเกตว่าเปลี่ยนจาก line["bbox"] เป็น custom_bbox
                        found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=custom_bbox))
                    # =================================================

                    prev_text = "paragraph" 
                    continue
        # -------------------------------------------------------------
        
        # --- ให้ระบบจำพิกัดข้อความของบรรทัดแรกเอาไว้ใช้ ---
        if b_type == "image_table" or line_text.startswith("รูปที่") or line_text.startswith("ตารางที่"):
            active_caption_indent = text_dist_mm
        # -------------------------------------------------------------

        # ถ้า suffix หลัง prefix ขึ้นต้นด้วย unit → เป็นค่าวัด ไม่ใช่หัวข้อ
        if ignored_units and prefix_str and b_type == "section":
            suffix_text = line_text.replace(prefix_str, "", 1).strip()
            if any(suffix_text.startswith(u) or suffix_text == u for u in ignored_units):
                prev_text = line_text
                continue
        
        # กำหนดเป้าหมาย (Rules) ตามประเภทที่ Regex ตรวจเจอ
        target_num = None
        target_text = None

        if b_type == "section":
            target_num = rules.get("main_heading_num", 0.0)
            target_text = rules.get("main_heading_text", 10.0)
            
            # [เพิ่มบรรทัดนี้] จำระยะข้อความของหัวข้อหลัก (เช่น 1.1) ไว้ให้ลูกใช้
            state.last_heading_text_indent = target_text

            # ตรวจสอบตัวหนา
            if not is_bold(line):
                found_issues.append(Issue(
                    page=page_num, 
                    code="FONT_STYLE_ERR", 
                    message=f"หัวข้อสำคัญ ({prefix_str}) ต้องเป็นตัวหนา", 
                    bbox=line["bbox"]
                ))
        elif b_type == "sub_section":
            target_num = rules.get("sub_heading_num", 10.0)
            
            try:
                parts = prefix_str.split(".")
                # นับความยาวจากส่วนประกอบที่ split ออกมาจริงๆ
                mid_digits  = len(parts[1]) if len(parts) > 1 else 1
                last_digits = len(parts[2]) if len(parts) > 2 else 1 # ใช้ index 2 สำหรับ X.X.10
            except (IndexError, AttributeError):
                mid_digits, last_digits = 1, 1

            if mid_digits >= 2 and last_digits >= 2:
                target_text = rules.get("sub_heading_text_3", 24.5)
            elif mid_digits >= 2 or last_digits >= 2:
                target_text = rules.get("sub_heading_text_2", 22.5)
            else:
                target_text = rules.get("sub_heading_text_1", 20.0)
                
            # [เพิ่มบรรทัดนี้] จำระยะข้อความของหัวข้อรอง (เช่น 1.1.1) ไว้ให้ลูกใช้
            state.last_heading_text_indent = target_text
            
        elif b_type == "sub_sub_section":
            target_num = state.last_heading_text_indent
            target_text = rules.get("list_item_text_1", 25.0) if digits == 1 else rules.get("list_item_text_2", 27.6)
            
        elif b_type == "bullet":
            target_num = rules.get("bullet_point", 25.0)
            target_text = rules.get("bullet_text", 30.0)
        elif b_type == "dash":
            target_num = rules.get("dash_indent", 30.0)
            target_text = rules.get("dash_text", 35.0)
            
        elif b_type == "paragraph":
            # --- บรรทัดแรกใต้หัวข้อสำคัญ (3.2): ต้อง indent ตรงกับ text target ของหัวข้อ ---
            heading_text_target = None
            if prev_b_type == "section":
                heading_text_target = rules.get("main_heading_text", 10.0)

            if heading_text_target is not None:
                # บังคับ paragraph แรกใต้หัวข้อสำคัญให้ตรงกับ text indent ของหัวข้อนั้น
                if abs(dist_mm - heading_text_target) > tolerance:
                    msg = (f"ข้อความหลังหัวข้อ ({prev_b_type}) ผิดตำแหน่ง: "
                           f"เริ่มที่ {dist_mm:.1f}mm (เป้าหมาย {heading_text_target}mm)")
                    found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=line["bbox"]))
            else:
                # paragraph ทั่วไป (ไม่ใช่บรรทัดแรกใต้หัวข้อ)
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

        # ตรวจสอบและบันทึก Issue
        if target_num is not None:
            if abs(dist_mm - target_num) > tolerance:
                msg = f"ระยะเยื้องผิด ({b_type}): เริ่มที่ {dist_mm:.1f}mm (เป้าหมาย {target_num}mm)"
                found_issues.append(Issue(page=page_num, code="INDENT_ERR", message=msg, bbox=line["bbox"]))

        if target_text is not None and text_x0 is not None:
            text_dist_mm = to_mm(text_x0 - m_left)
            if abs(text_dist_mm - target_text) > tolerance:
                msg = f"ข้อความหลัง {prefix_str} ผิดตำแหน่ง: เริ่มที่ {text_dist_mm:.1f}mm (เป้าหมาย {target_text}mm)"
                found_issues.append(Issue(page=page_num, code="TEXT_ALIGN_ERR", message=msg, bbox=line["bbox"]))
                
        # === [เพิ่ม 2 บรรทัดนี้] สร้างสมองก้อนใหม่ จำระยะข้อความล่าสุดไว้ใช้กับย่อหน้า ===
        if target_text is not None:
            state.last_text_target = target_text
        # =========================================================

        prev_text = line_text     # เดิน local prev tracking ภายใน loop นี้
        prev_b_type = b_type      # เก็บ b_type ของบรรทัดนี้ไว้สำหรับบรรทัดถัดไป
        prev_l_bbox = l_bbox      # <--- [เพิ่มบรรทัดนี้] เก็บพิกัดไว้ให้ลูปรอบถัดไปเช็คต่อ

    return found_issues