import re
from typing import List, Tuple, Optional
from config import THAI_SEQ

# --- ANSI Colors & Styles for Terminal Output ---
RED = '\033[91m'      # Error / Fail / Critical
GREEN = '\033[92m'    # Success / Pass
YELLOW = '\033[93m'   # Warning
BLUE = '\033[94m'     # Info / Structure / Logic
MAGENTA = '\033[95m'  # Title / Chapter / Special Event
CYAN = '\033[96m'     # Debug / Path / Filename
WHITE = '\033[97m'    # Text (Bright)

# --- Text Styles ---
BOLD = '\033[1m'      # ตัวหนา (เหมาะกับหัวข้อ)
UNDERLINE = '\033[4m' # ขีดเส้นใต้ (เหมาะกับชื่อไฟล์หรือ Link)
RST = '\033[0m'       # Reset (คืนค่าเดิม)

def mm_to_pt(v): 
    """ mm to pt """
    return v * (72 / 25.4)

def pt_to_mm(v): 
    """ pt to mm """
    return v / (72 / 25.4)

def parse_sub_section_bullet(text: str) -> Optional[int]:
    """ตรวจสอบหัวข้อย่อยแบบตัวเลขมีวงเล็บปิด (เช่น 1), 10)) และคืนค่าจำนวนหลักของตัวเลข"""
    # ค้นหารูปแบบ ตัวเลข ตามด้วยเครื่องหมายวงเล็บปิด ) ที่ต้นบรรทัด
    match = re.match(r"^(\d+)\)", text)
    if match: 
        return len(match.group(1)) # คืนค่าจำนวนหลัก เพื่อใช้กำหนดระยะเยื้องของชื่อหัวข้อต่อ
    return None

# def check_sequence_logic(prev: List[int], curr: List[int]) -> Tuple[bool, str]:
#     """ตรวจสอบความถูกต้องของลำดับหมายเลขหัวข้อ (1.1 -> 1.2)"""
#     # เช็คเลขซ้ำ
#     if prev == curr:
#         return True, f"เลขหัวข้อซ้ำ: {'.'.join(map(str, curr))}"
    
#     # เช็คการถอยหลัง
#     if curr < prev:
#         return True, f"ลำดับหัวข้อย้อนกลับ: เจอ {'.'.join(map(str, curr))} ต่อจาก {'.'.join(map(str, prev))}"
    
#     # เช็คการกระโดดข้ามลำดับ
#     diff_idx = -1
#     for i in range(min(len(prev), len(curr))):
#         if prev[i] != curr[i]:
#             diff_idx = i
#             break
            
#     if diff_idx != -1:
#         if curr[diff_idx] - prev[diff_idx] > 1:
#             return True, f"เลขหัวข้อกระโดดผิดปกติ (Warning): {'.'.join(map(str, prev))} -> {'.'.join(map(str, curr))}"
            
    return False, ""

def parse_section_number(text: str) -> Optional[List[int]]:
    """
    แกะเลขหัวข้อจากข้อความ คืนค่า None ถ้าขึ้นต้นบรรทัดไม่ใช่รูปแบบตัวเลข
    """
    if not text:
        return None
    
    # [FIX] ใช้ Regex ดึงเฉพาะก้อนตัวเลขจากต้นบรรทัดโดยไม่สนใจว่าจะมีเว้นวรรคตามหลังหรือไม่
    # เผื่อกรณี PDF แกะข้อความมาติดกัน เช่น "1.1.1หัวข้อรอง"
    match = re.match(r"^(\d+(?:\.\d+)*\.?)", text.strip())
    if not match:
        return None
        
    first_token = match.group(1)

    try:
        numbers = [int(x) for x in first_token.split('.') if x]
        return numbers
    except ValueError:
        return None


def check_sequence_logic(prev: List[int], curr: List[int]) -> Tuple[bool, str]:
    """ตรวจสอบความถูกต้องของลำดับหมายเลขหัวข้อ"""
    if prev == curr:
        return True, f"เลขหัวข้อซ้ำ: {'.'.join(map(str, curr))}"
    
    if curr < prev:
        return True, f"ลำดับหัวข้อย้อนกลับ: เจอ {'.'.join(map(str, curr))} ต่อจาก {'.'.join(map(str, prev))}"
    
    diff_idx = -1
    for i in range(min(len(prev), len(curr))):
        if prev[i] != curr[i]:
            diff_idx = i
            break
            
    if diff_idx == -1:
        # [FIX] กรณีที่เลขชุดหน้าเหมือนกัน แต่ curr ยาวกว่า (เช่น 1.1 -> 1.1.3)
        if len(curr) > len(prev):
            # เช็คว่าเลขตัวที่งอกมาใหม่ ต้องเป็น 1 เท่านั้น
            if curr[len(prev)] > 1:
                return True, f"เลขหัวข้อย่อยกระโดดผิดปกติ (Warning): {'.'.join(map(str, prev))} -> {'.'.join(map(str, curr))}"
            # เช็คว่าลึกเกินไปหรือไม่ (เช่น 1.1 -> 1.1.1.1)
            if len(curr) > len(prev) + 1:
                return True, f"ระดับหัวข้อย่อยลึกเกินไป (Warning): {'.'.join(map(str, prev))} -> {'.'.join(map(str, curr))}"
    else:
        # กรณีที่เลขต่างกันที่ตำแหน่ง diff_idx
        if curr[diff_idx] - prev[diff_idx] > 1:
            return True, f"เลขหัวข้อกระโดดผิดปกติ (Warning): {'.'.join(map(str, prev))} -> {'.'.join(map(str, curr))}"
        
        # [ADD-ON] เช็คความลึกที่ตามหลังจุดที่ต่างกัน ต้องเริ่มด้วย 1 เสมอ 
        # (เช่น 1.1.2 ไป 1.2.2 จะผิด เพราะต้องเริ่มที่ 1.2.1)
        for j in range(diff_idx + 1, len(curr)):
            if curr[j] > 1:
                return True, f"เลขหัวข้อย่อยเริ่มต้นผิด ต้องเริ่มที่ 1 (Warning): {'.'.join(map(str, prev))} -> {'.'.join(map(str, curr))}"

    return False, ""
