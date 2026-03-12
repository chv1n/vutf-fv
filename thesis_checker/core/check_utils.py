from    config import PATTERNS
import  fitz
import  re

def get_prefix_and_text_coords(line_raw: dict):
    all_chars = [c for s in line_raw["spans"] for c in s["chars"]]
    full_text_raw = "".join([c["c"] for c in all_chars])
    full_text = full_text_raw.strip()

    for b_type, regex in PATTERNS.items():
        match = re.search(regex, full_text)
        if match:
            prefix_str = match.group(1)
            
            # --- บังคับว่า prefix ต้องอยู่หน้าสุดของข้อความ ---
            if not full_text.startswith(prefix_str):
                continue  # ถ้าไม่ใช่คำแรกของบรรทัด ให้ข้ามไปเลย ถือว่าเป็นแค่ประโยคธรรมดา

            # --- Validate numeric ranges เพื่อกรอง false positive ---
            if b_type == "section":
                parts = prefix_str.split(".")
                try:
                    chap_num = int(parts[0])
                    sec_num  = int(parts[1])
                    # เลขบทต้อง 1-10, เลขหัวข้อต้อง 1-19
                    if chap_num < 1 or chap_num > 10 or sec_num >= 20:
                        continue  # ไม่ใช่หัวข้อจริง → ตรวจ pattern ถัดไป
                except (ValueError, IndexError):
                    continue

            if b_type == "sub_section":
                parts = prefix_str.split(".")
                try:
                    chap_num = int(parts[0])
                    sec_num  = int(parts[1])
                    sub_num  = int(parts[2])
                    # เลขบท 1-5, เลขหัวข้อ 1-19, เลขรอง 1-19
                    if chap_num < 1 or chap_num > 5 or sec_num >= 20 or sub_num >= 20:
                        continue
                except (ValueError, IndexError):
                    continue
            
            # คำนวณ digits จาก Group ที่เราดักไว้
            digits = 0
            if b_type in ["sub_section", "sub_sub_section"]:
                digits = len(match.group(2))
            
            start_idx = full_text_raw.find(prefix_str)
            
            if start_idx == -1:
                start_idx = 0
            
            end_idx = start_idx + len(prefix_str)
            
            p_rect = fitz.Rect()
            for i in range(start_idx, end_idx):
                p_rect.include_rect(all_chars[i]["bbox"])
            
            text_start_idx = end_idx
            while text_start_idx < len(all_chars) and not all_chars[text_start_idx]["c"].strip():
                text_start_idx += 1
            
            t_rect = fitz.Rect()
            if text_start_idx < len(all_chars):
                for i in range(text_start_idx, len(all_chars)):
                    t_rect.include_rect(all_chars[i]["bbox"])

            return {
                "type": b_type,
                "prefix": prefix_str,
                "digits": digits,
                "prefix_x0": p_rect.x0,
                "text_x0": t_rect.x0 if not t_rect.is_empty else None
            }

    return {"type": "paragraph", "prefix": "", "digits": 0, "prefix_x0": line_raw["bbox"][0], "text_x0": None}

def is_bold(line: dict) -> bool:
    """ตรวจว่าในบรรทัดนั้นมี spans ที่เป็นตัวหนาหรือไม่"""
    for span in line.get("spans", []):
        # เช็คจาก flags (Bit 4: bold, Bit 1: italic)
        if span.get("flags", 0) & 2**4: 
            return True
            
    return False

def is_formula(text: str) -> bool:
    """ตรวจว่าข้อความเป็นสูตร/สมการหรือไม่"""
    
    # 1. กฎเหล็ก: นับสัดส่วนตัวอักษรไทยก่อนเป็นอันดับแรก
    thai_chars = len(re.findall(r'[\u0E00-\u0E7F]', text))
    total_chars = len(text.replace(' ', ''))
    
    if total_chars == 0:
        return False
        
    # ถ้ามีภาษาไทยปนอยู่เยอะ (ตั้งแต่ 30% ขึ้นไป) ให้ฟันธงว่าเป็นข้อความธรรมดา ไม่ใช่สมการ
    if (thai_chars / total_chars) >= 0.3:
        return False

    # 2. ถ้าหลุดรอดกฎเหล็กมาได้ (แปลว่าภาษาไทยน้อย) ค่อยมาเช็คว่าเป็นสมการหรือไม่
    
    # มีเครื่องหมาย = ที่ไม่ใช่เปรียบเทียบ
    if '=' in text and len(text) < 200:
        return True
    
    # มีสัญลักษณ์คณิตศาสตร์ เช่น ×, ÷, ±, ≤, ≥, ∑, ∫, √, Δ, α, β
    math_symbols = set('×÷±≤≥≠∑∫√∆∞αβγδεζηθλμπσφωΩ')
    if any(c in math_symbols for c in text):
        return True
    
    # ข้อความสั้นที่มี operator ทางคณิตศาสตร์เยอะ (เช่น "P = V * I")
    if len(text) < 100:
        math_ops = len(re.findall(r'[+\-*/=<>^²³]', text))
        if math_ops >= 2:
            return True
            
    return False

def get_line_text_from_raw(line_data: dict) -> str:
    """
    ดึงข้อความทั้งบรรทัดจากโครงสร้าง rawdict
    """
    line_text = ""
    for span in line_data.get("spans", []):
        # ใน rawdict เราต้องวนลูปดึงค่า 'c' (character) จาก list 'chars'
        span_text = "".join([char["c"] for char in span.get("chars", [])])
        line_text += span_text
    return line_text

def extract_prefix_and_text_bboxes(line_raw: dict, prefix_str: str):
    """
    คืนค่า (prefix_bbox, text_bbox) โดยคำนวณจากรายตัวอักษร (rawdict)
    """
    # รวมตัวอักษรทั้งหมดจากทุก spans ในบรรทัดนี้มาไว้ที่เดียว
    all_chars = []
    for span in line_raw.get("spans", []):
        all_chars.extend(span.get("chars", []))
    
    if not all_chars:
        return None, None

    # สร้าง str ทั้งหมดเพื่อหาตำแหน่ง index
    full_text = "".join([c["c"] for c in all_chars])
    
    # หาตำแหน่งที่ Prefix อยู่ (เผื่อมีช่องว่างนำหน้า)
    prefix_start_idx = full_text.find(prefix_str)
    if prefix_start_idx == -1:
        return line_raw["bbox"], None # หาไม่เจอให้คืนค่าทั้งบรรทัด
        
    prefix_end_idx = prefix_start_idx + len(prefix_str)
    
    # คำนวณ Bbox ของ Prefix (รวม '1' '.' '2')
    p_rect = fitz.Rect()
    for i in range(prefix_start_idx, prefix_end_idx):
        p_rect.include_rect(all_chars[i]["bbox"])
        
    # หาจุดเริ่มของ Text (ข้ามช่องว่างหลัง Prefix)
    text_start_idx = prefix_end_idx
    while text_start_idx < len(all_chars) and not all_chars[text_start_idx]["c"].strip():
        text_start_idx += 1
        
    # คำนวณ Bbox ของ Text 
    t_rect = fitz.Rect()
    for i in range(text_start_idx, len(all_chars)):
        # ข้ามช่องว่างปิดท้าย
        if all_chars[i]["c"].strip():
            t_rect.include_rect(all_chars[i]["bbox"])

    # คืนค่าเป็น List [x0, y0, x1, y1] หรือ None ถ้าไม่มีข้อมูล
    return (list(p_rect) if not p_rect.is_empty else None, 
            list(t_rect) if not t_rect.is_empty else None)