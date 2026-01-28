import re
from typing import List, Tuple, Optional
from models import Issue
from utils import parse_section_number, check_sequence_logic

def check_section_rules(
    page_num: int, 
    line_text: str, 
    bbox: list, 
    chapter_num: int, 
    last_section_nums: Optional[List[int]],
    ignored_units: List[str] = []  # <--- รับค่าจาก Config
) -> Tuple[List[Issue], Optional[List[int]]]:
    
    found_issues = []
    updated_last_nums = last_section_nums

    curr_sec = parse_section_number(line_text) 
    
    if curr_sec:
        
        # =========================================================
        # Noise Filters
        # =========================================================
        
        # 1. กรองเลขที่ขึ้นต้นด้วย 0
        if curr_sec[0] == 0:
            return found_issues, updated_last_nums

        sec_str = ".".join(map(str, curr_sec))
        
        # 2. กรอง % (เปอร์เซ็นต์)
        if re.match(rf"^{re.escape(sec_str)}\s*%", line_text):
            return found_issues, updated_last_nums

        # 3. กรองหน่วยวัด (Load จาก Config)
        if ignored_units:
            # สร้าง Regex Pattern: (m|cm|mm|...) โดย escape ตัวอักษรพิเศษให้ด้วย (เช่น °C)
            units_pattern = "|".join([re.escape(u) for u in ignored_units])
            
            # Regex: เลข + เว้นวรรค(opt) + (หน่วยใดหน่วยหนึ่ง) + (จบคำ/จบประโยค)
            # เพิ่ม \b หรือ regex boundary เพื่อความชัวร์ว่าจบคำจริงๆ หรือตามด้วย symbol อื่น
            full_regex = rf"^{re.escape(sec_str)}\s*({units_pattern})(\s|$|\W)"
            
            if re.match(full_regex, line_text):
                 return found_issues, updated_last_nums

        # =========================================================
        # Logic การตรวจปกติ
        # =========================================================
        
        if curr_sec[0] != chapter_num:
             found_issues.append(Issue(
                page_num, 
                "SECTION_PREFIX_ERR", 
                f"หัวข้อผิดบท: ต้องขึ้นด้วย {chapter_num}. (เจอ {line_text.split()[0]})", 
                bbox=bbox
            ))
        else:
            if last_section_nums:
                is_issue, msg = check_sequence_logic(last_section_nums, curr_sec)
                if is_issue:
                    found_issues.append(Issue(page_num, "SECTION_SEQ_ERR", msg, bbox=bbox))
            
            updated_last_nums = curr_sec

    return found_issues, updated_last_nums