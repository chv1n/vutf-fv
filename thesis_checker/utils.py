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

def mm(v): 
    """ mm to pt """
    return v * (72 / 25.4)

def to_mm(v): 
    """ pt to mm """
    return v / (72 / 25.4)

def parse_sub_section_bullet(text: str) -> Optional[int]:
    """ตรวจสอบหัวข้อย่อยแบบตัวเลขมีวงเล็บปิด (เช่น 1), 10)) และคืนค่าจำนวนหลักของตัวเลข"""
    # ค้นหารูปแบบ ตัวเลข ตามด้วยเครื่องหมายวงเล็บปิด ) ที่ต้นบรรทัด
    match = re.match(r"^(\d+)\)", text)
    if match: 
        return len(match.group(1)) # คืนค่าจำนวนหลัก เพื่อใช้กำหนดระยะเยื้องของชื่อหัวข้อต่อ
    return None

def check_sequence_logic(prev: List[int], curr: List[int]) -> Tuple[bool, str]:
    """ตรวจสอบความถูกต้องของลำดับหมายเลขหัวข้อ (1.1 -> 1.2)"""
    # 1. เช็คเลขซ้ำ
    if prev == curr:
        return True, f"เลขหัวข้อซ้ำ: {'.'.join(map(str, curr))}"
    
    # 2. เช็คการถอยหลัง
    if curr < prev:
        return True, f"ลำดับหัวข้อย้อนกลับ: เจอ {'.'.join(map(str, curr))} ต่อจาก {'.'.join(map(str, prev))}"
    
    # 3. เช็คการกระโดดข้ามลำดับ
    diff_idx = -1
    for i in range(min(len(prev), len(curr))):
        if prev[i] != curr[i]:
            diff_idx = i
            break
            
    if diff_idx != -1:
        if curr[diff_idx] - prev[diff_idx] > 1:
            return True, f"เลขหัวข้อกระโดดผิดปกติ (Warning): {'.'.join(map(str, prev))} -> {'.'.join(map(str, curr))}"
            
    return False, ""

def parse_section_number(text: str) -> Optional[List[int]]:
    """
    แกะเลขหัวข้อจากข้อความ เช่น "2.1.3 ผลการทดลอง" -> [2, 1, 3]
    คืนค่า None ถ้าขึ้นต้นบรรทัดไม่ใช่รูปแบบตัวเลข
    """
    if not text:
        return None
    
    # 1. ดึงคำแรกสุดของบรรทัดออกมา (เพราะเลขหัวข้อต้องอยู่หน้าสุดเสมอ)
    # เช่น "2.1.3 ผลการทดลอง" -> "2.1.3"
    words = text.strip().split()
    if not words:
        return None
    
    first_token = words[0]

    # 2. ตรวจสอบ Pattern ว่าใช่รูปแบบเลขหัวข้อหรือไม่
    # Regex: ขึ้นต้นด้วยเลข, ตามด้วย (จุด+เลข) ซ้ำๆ, และอาจจบด้วยจุด
    # เช่น "1", "1.1", "2.1.3", "2.1.3."
    if not re.match(r"^\d+(\.\d+)*\.?$", first_token):
        return None

    # 3. แปลงเป็น List[int]
    try:
        # split('.') จะได้เช่น "2.1.3." -> ['2', '1', '3', '']
        # ใช้ if x เพื่อกรองตัวว่าง ('') ทิ้งไป
        numbers = [int(x) for x in first_token.split('.') if x]
        return numbers
    except ValueError:
        return None
