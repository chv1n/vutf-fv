import re
from typing import List, Tuple, Optional
from models import Issue, ThesisState

def check_section_sequence(state: ThesisState, current_chapter: int, b_type: str, prefix_str: str, line_text: str, ignored_units: list = None) -> Optional[str]:

    prev_text = state.prev_line_text.strip()
    suffix_text = line_text.replace(prefix_str, "").strip()
    
    # ดักเคสรูปภาพแยกบรรทัด
    is_split_start = (prev_text == "รูปที่" or prev_text == "ตารางที่")
    is_ghost_number = (len(suffix_text) < 2) and ("รูปที่" in prev_text or "ตารางที่" in prev_text)

    if is_split_start or is_ghost_number:
        return None 

    if prev_text.strip().endswith(("รูปที่", "ตารางที่", "สมการที่", "และ", "จาก")):
        return None

    # เพิ่ม sub_sub_section เข้าไป เพื่อดักเคส 2) โดดๆ จากสมการ
    if b_type in ["section", "sub_section", "sub_sub_section"] and not suffix_text:
        return None

    # ถ้า suffix ขึ้นต้นด้วย unit (เช่น "V", "kHz", "%", "m/s")
    if ignored_units and b_type == "section":
        for unit in ignored_units:
            if suffix_text == unit or suffix_text.startswith(unit + " ") or suffix_text.startswith(unit + "."):
                return None

    nums = state.extract_numbers(prefix_str)
    if not nums: 
        return None

    error_msg = None

    if b_type == "section":
        if len(nums) < 2: return None
        curr_chap, curr_main = nums[0], nums[1]

        # เช็คด้วย current_chapter ที่ส่งเข้ามา
        if current_chapter != 0 and curr_chap != current_chapter:
            error_msg = f"หัวข้อผิดบท: คาดหวัง {current_chapter}.X แต่พบ {prefix_str}"
        else:
            expected_main = state.last_main_sec[1] + 1 if state.last_main_sec else 1
            if curr_main != expected_main:
                error_msg = f"ลำดับหัวข้อสำคัญผิด: คาดหวัง {curr_chap}.{expected_main} แต่พบ {prefix_str}"

        state.set_new_main_sec(nums)
        return error_msg

    elif b_type == "sub_section":
        if len(nums) < 3: return None
        curr_chap, curr_main, curr_sub = nums[0], nums[1], nums[2]

        expected_main = state.last_main_sec[1] if state.last_main_sec else 1
        # เช็คด้วย current_chapter ที่ส่งเข้ามา
        if curr_chap != current_chapter or curr_main != expected_main:
            error_msg = f"หัวข้อรองผิดกลุ่ม: คาดหวังให้อยู่ภายใต้ {current_chapter}.{expected_main} แต่พบ {prefix_str}"
        else:
            expected_sub = state.last_sub_sec[2] + 1 if state.last_sub_sec else 1
            if curr_sub != expected_sub:
                error_msg = f"ลำดับหัวข้อรองผิด: คาดหวัง {curr_chap}.{curr_main}.{expected_sub} แต่พบ {prefix_str}"

        state.set_new_sub_sec(nums)
        return error_msg

    elif b_type == "sub_sub_section":
        curr_list = nums[0]
        expected_list = state.last_list_num + 1 if state.last_list_num else 1
        
        if curr_list != expected_list:
            if state.last_list_num is None:
                error_msg = f"รายการย่อยเริ่มผิด: ต้องเริ่มที่ 1) แต่พบ {prefix_str}"
            else:
                error_msg = f"ลำดับรายการย่อยผิด: คาดหวัง {expected_list}) แต่พบ {prefix_str}"

        state.set_new_list_num(curr_list)
        return error_msg

    return None