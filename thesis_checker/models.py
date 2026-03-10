import re
from dataclasses import dataclass
from typing import Tuple, Optional, List

@dataclass
class Issue:
    page: int
    code: str
    message: str
    severity: str = "error"
    bbox: Optional[Tuple[float, float, float, float]] = None


class ThesisState:
    def __init__(self):
        self.last_main_sec: Optional[List[int]] = None  
        self.last_sub_sec: Optional[List[int]] = None   
        self.last_list_num: Optional[int] = None   
        
        self.prev_line_text = ""

        self.last_heading_type = "paragraph"
        self.last_heading_text_indent = 20.0

    def update_prev_text(self, text: str):
        self.prev_line_text = text.strip()

    def reset_for_new_chapter(self):
        """เรียกใช้เมื่อ detect_chapter เปลี่ยนบท"""
        self.last_main_sec = None
        self.last_sub_sec = None
        self.last_list_num = None

        self.prev_line_text = ""

    def set_new_main_sec(self, nums: List[int]):
        self.last_main_sec = nums
        self.last_sub_sec = None
        self.last_list_num = None

    def set_new_sub_sec(self, nums: List[int]):
        self.last_sub_sec = nums
        self.last_list_num = None
        
    def set_new_list_num(self, num: int):
        self.last_list_num = num

    def extract_numbers(self, prefix_str: str) -> List[int]:
        thai_nums = "๐๑๒๓๔๕๖๗๘๙"
        arabic_nums = "0123456789"
        trans = str.maketrans(thai_nums, arabic_nums)
        clean_str = prefix_str.translate(trans)
        return [int(n) for n in re.findall(r'\d+', clean_str)]

def check_section_sequence(state: ThesisState, current_chapter: int, b_type: str, prefix_str: str) -> Optional[str]:
    """รับ current_chapter ที่ได้จาก detect_chapter เข้ามาเป็นอาร์กิวเมนต์"""
    nums = state.extract_numbers(prefix_str)
    if not nums: return None

    error_msg = None

    if b_type == "section":
        if len(nums) < 2: return None
        curr_chap, curr_main = nums[0], nums[1]

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