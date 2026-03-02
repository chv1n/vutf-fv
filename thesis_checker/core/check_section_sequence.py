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
    last_paren_num: Optional[int] = None,
    ignored_units: List[str] = [],
    prev_line_text: str = ""
) -> Tuple[List[Issue], Optional[List[int]], Optional[int]]:
    
    found_issues = []
    updated_last_nums = last_section_nums
    updated_paren_num = last_paren_num

    stripped = line_text.strip()
    paren_match = re.match(r"^(\d+)\)", stripped)
    if paren_match:
        curr_paren = int(paren_match.group(1))
        
        if curr_paren > 50:
            return found_issues, updated_last_nums, updated_paren_num
        
        after_paren = stripped[paren_match.end():]
        if re.match(r"^\s*[+\-*/=<>^]", after_paren):
            return found_issues, updated_last_nums, updated_paren_num

        # print(f"  [PAREN MATCH] page={page_num} | num={curr_paren}) | last={last_paren_num} | text='{stripped[:60]}'")
        
        if last_paren_num is not None:
            diff = curr_paren - last_paren_num
            if diff > 1:
                found_issues.append(Issue(
                    page_num,
                    "SECTION_SEQ_ERR",
                    f"เลขหัวข้อย่อยกระโดด: {last_paren_num}) -> {curr_paren})",
                    bbox=bbox
                ))
            elif curr_paren == last_paren_num:
                found_issues.append(Issue(
                    page_num,
                    "SECTION_SEQ_ERR",
                    f"เลขหัวข้อย่อยซ้ำ: {curr_paren})",
                    bbox=bbox
                ))
            elif curr_paren < last_paren_num and curr_paren != 1:
                found_issues.append(Issue(
                    page_num,
                    "SECTION_SEQ_ERR",
                    f"ลำดับหัวข้อย่อยย้อนกลับ: {last_paren_num}) -> {curr_paren})",
                    bbox=bbox
                ))
        else:
            if curr_paren != 1:
                found_issues.append(Issue(
                    page_num,
                    "SECTION_SEQ_ERR",
                    f"หัวข้อย่อยเริ่มผิด: ต้องเริ่มที่ 1) (เจอ {curr_paren}))",
                    bbox=bbox
                ))
        updated_paren_num = curr_paren
        return found_issues, updated_last_nums, updated_paren_num

    curr_sec = parse_section_number(line_text) 
    
    if curr_sec:
        if curr_sec[0] == 0:
            return found_issues, updated_last_nums, updated_paren_num

        if curr_sec[0] > 10 or any(n > 50 for n in curr_sec[1:]):
            return found_issues, updated_last_nums, last_paren_num

        sec_str = ".".join(map(str, curr_sec))
        
        if re.match(r"^\d+(?:\.\d+)+\s*%", line_text):
            return found_issues, updated_last_nums, last_paren_num

        if ignored_units:
            units_pattern = "|".join([re.escape(u) for u in ignored_units])
            full_regex = rf"^\d+(?:\.\d+)+\s*({units_pattern})(\s|$|\W)"
            if re.search(full_regex, line_text):
                 return found_issues, updated_last_nums, last_paren_num

        if prev_line_text:
            if prev_line_text.strip().endswith(("รูปที่", "ตารางที่", "สมการที่", "บทที่", "ข้อที่", "ดังรูป", "ในรูป", "ตาราง")):
                return found_issues, updated_last_nums, last_paren_num

        if line_text.strip() == sec_str:
            return found_issues, updated_last_nums, last_paren_num

        if len(curr_sec) < 2:
            return found_issues, updated_last_nums, last_paren_num

        if last_paren_num is not None:
            print(f"  [PAREN RESET] page={page_num} | '{line_text.strip()[:40]}' reset paren {last_paren_num} -> None")
        updated_paren_num = None

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

    return found_issues, updated_last_nums, updated_paren_num