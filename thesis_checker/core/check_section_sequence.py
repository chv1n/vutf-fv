import re  # <--- อย่าลืม import re ที่หัวไฟล์
from typing import List, Tuple, Optional
from models import Issue
from utils import parse_section_number, check_sequence_logic

def check_section_rules(
    page_num: int, 
    line_text: str, 
    bbox: list, 
    chapter_num: int, 
    last_section_nums: Optional[List[int]]
) -> Tuple[List[Issue], Optional[List[int]]]:
    
    found_issues = []
    updated_last_nums = last_section_nums

    curr_sec = parse_section_number(line_text) 
    
    if curr_sec:
        # =========================================================
        # [NEW] Noise Filters: กรองสิ่งที่ไม่ใช่หัวข้อออกไปก่อน
        # =========================================================
        
        # 1. กรองเลขที่ขึ้นต้นด้วย 0 (เช่น 0.45, 0.54) -> หัวข้อบทไม่มีทางเริ่มด้วย 0
        if curr_sec[0] == 0:
            return found_issues, updated_last_nums

        # สร้าง string ของเลขที่จับได้เพื่อเช็คบริบท (เช่น [14, 256] -> "14.256")
        sec_str = ".".join(map(str, curr_sec))
        
        # 2. กรองถ้าตามหลังด้วย % ทันที (เช่น 2.50%, 0.45%)
        # เช็คทั้งแบบติดกัน (2.50%) และมีเว้นวรรค (2.50 %)
        if re.match(rf"^{re.escape(sec_str)}\s*%", line_text):
            return found_issues, updated_last_nums

        # 3. กรองถ้าตามหลังด้วยหน่วยวัดทางวิศวกรรม (เช่น 0.54 m, 14.256 MJ)
        # Regex: ขึ้นต้นด้วยเลข + เว้นวรรค(option) + หน่วย + (จบประโยค หรือ เว้นวรรค)
        # หน่วยที่พบบ่อย: m, cm, mm, kg, A, V, W, Hz, MJ, J, degree, etc.
        # [Image_7c5967.png] เจอหน่วย MJ//m2-day ก็จะถูกกรองด้วย MJ
        common_units = r"(m|cm|mm|km|kg|g|mg|A|V|W|kW|MW|Hz|kHz|MHz|GHz|J|MJ|°C|K|N|Pa|bar)"
        if re.match(rf"^{re.escape(sec_str)}\s*{common_units}(\s|$|\W)", line_text):
             return found_issues, updated_last_nums

        # =========================================================

        # --- เข้าสู่ Logic การตรวจปกติ ---
        
        # 1. เช็คเลขนำหน้า (Prefix) ว่าตรงกับบทไหม
        if curr_sec[0] != chapter_num:
            # เพิ่มการเช็ค: ถ้าเลขบทต่างกันมากๆ (เช่น บท 2 แต่เจอเลข 14.xxx) 
            # อาจจะเป็นตัวเลขในตาราง ไม่ใช่หัวข้อ -> อาจเลือกที่จะ ignore หรือแจ้ง warning
            # แต่ถ้าเป็น Thesis ปกติ หัวข้อย่อยไม่ควรข้ามไปเลข 14 ดังนั้นแจ้ง Error ไว้ก่อนปลอดภัยกว่า
            found_issues.append(Issue(
                page_num, 
                "SECTION_PREFIX_ERR", 
                f"หัวข้อผิดบท: ต้องขึ้นด้วย {chapter_num}. (เจอ {line_text.split()[0]})", 
                bbox=bbox
            ))
        else:
            # 2. เช็คความต่อเนื่อง (Sequence)
            if last_section_nums:
                is_issue, msg = check_sequence_logic(last_section_nums, curr_sec)
                if is_issue:
                    found_issues.append(Issue(page_num, "SECTION_SEQ_ERR", msg, bbox=bbox))
            
            # อัปเดตเลขล่าสุดเฉพาะเมื่อเป็นเลขที่ถูกต้อง
            updated_last_nums = curr_sec

    return found_issues, updated_last_nums