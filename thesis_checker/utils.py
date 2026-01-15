import re
from typing import List, Tuple, Optional
from config import THAI_SEQ

def mm(v): 
    """ mm to pt """
    return v * (72 / 25.4)

def to_mm(v): 
    """ pt to mm """
    return v / (72 / 25.4)

def get_next_thai(char):
    """หาตัวอักษรไทยลำดับถัดไป (เช่น ก -> ข) สำหรับตรวจลำดับหน้า"""
    try:
        idx = THAI_SEQ.index(char)
        if idx + 1 < len(THAI_SEQ): 
            return THAI_SEQ[idx + 1]
    except (ValueError, TypeError): 
        pass
    return None

def parse_section_number(text: str) -> Optional[List[int]]:
    """แปลงเลขหัวข้อแบบระบบทศนิยม (เช่น 1.1, 2.3.1) เป็น List ของตัวเลข"""
    # Regex สำหรับจับหัวข้อที่ขึ้นต้นบรรทัดและมีจุดอย่างน้อย 1 จุด
    SECTION_PATTERN = re.compile(r"^(\d+(?:\.\d+)+)")
    match = SECTION_PATTERN.match(text)
    if match:
        try: 
            return [int(x) for x in match.group(1).split('.')]
        except ValueError: 
            return None
    return None

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