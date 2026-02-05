import fitz
import re
import utils as u

def detect_current_chapter(page: fitz.Page, current_chapter_num: int) -> int:
    """
    ระบุส่วนต่างๆ ของเล่ม (1-9)
    โดยมีการกรองหน้า "สารบัญ" และ "หน้าที่มีเลข ก-ฮ" ออก
    """
    
    w = page.rect.width
    h = page.rect.height
    
    # 1. โซนตรวจจับส่วนหัว (20%)
    header_zone = fitz.Rect(0, 0, w, h * 0.2)
    header_text = page.get_text("text", clip=header_zone).strip()
    
    # 2. โซนตรวจจับกึ่งกลาง
    center_zone = fitz.Rect(0, h * 0.3, w, h * 0.7)
    center_text = page.get_text("text", clip=center_zone).strip()
    
    # ดึงเลขหน้าจากมุมขวาบน 
    # ใช้ logic เดียวกับ get_page_number_text แบบย่อ
    page_num_rect = fitz.Rect(w * 0.7, 0, w, h * 0.1) 
    page_num_text = page.get_text("text", clip=page_num_rect).strip()

    # [FILTER 1] กรองหน้าสารบัญ (Keywords)
    if "สารบัญ" in header_text:
        return current_chapter_num

    # [FILTER 2] กรองเลขหน้าไทย
    # ถ้าเจอก ไก่ - ฮ นกฮูก ในโซนเลขหน้า -> เป็นส่วนหน้าแน่นอน (Pre-content)
    # ห้ามเปลี่ยนไปเป็นบทอื่น (เช่น ภาคผนวก) แม้จะเจอ keyword ก็ตาม
    # Regex: เช็คว่าเป็นตัวอักษรไทย 1-3 ตัว (เผื่อ พ, ภ, ฦ) ไม่มีตัวเลขปน
    if re.search(r"^[ก-ฮ]{1,3}$", page_num_text):
        return 0 # หรือ return current_chapter_num

    # เพิ่มการเช็คใน header_text ด้วย (เผื่อเลขหน้าหลุดโซน)
    # เช็คว่ามีบรรทัดไหนที่เป็นตัวอักษรไทยโดดๆ หรือไม่
    lines = header_text.split('\n')
    for line in lines:
        if re.match(r"^\s*[ก-ฮ]{1,3}\s*$", line):
             return 0 # เจอเลขหน้าไทย -> บังคับเป็น Pre-content

    detected_chapter = current_chapter_num

    # Logic 1: ตรวจหา "บทที่ 1-5" (เช็ค Header)
    match_chapter = re.search(r"บทที่\s*(\d+)", header_text)
    if match_chapter:
        try:
            found_num = int(match_chapter.group(1))
            if 1 <= found_num <= 5:
                detected_chapter = found_num
        except ValueError:
            pass


    # Logic 2: ตรวจหา ส่วนท้ายเล่ม (Keywords)    
    # บรรณานุกรม
    elif "บรรณานุกรม" in header_text:
        detected_chapter = 6
    
    # ภาคผนวก ก
    elif "ภาคผนวก ก" in header_text or "ภาคผนวก ก" in center_text:
        # เช็คเพิ่ม: ต้องไม่ใช่บรรทัดที่มีจุดไข่ปลา (................) แบบในสารบัญ
        detected_chapter = 7
        
    # ภาคผนวก ข
    elif "ภาคผนวก ข" in header_text or "ภาคผนวก ข" in center_text:
        detected_chapter = 8
        
    # ประวัติผู้จัดทำ
    elif "ประวัติผู้จัดทำ" in header_text or "ประวัติผู้จัดทำ" in center_text:
        detected_chapter = 9

    # Print Debug (เฉพาะตอนเปลี่ยนบท)
    if detected_chapter != current_chapter_num:
        msg = ""
        if 1 <= detected_chapter <= 5:
            msg = f">>> Detected Start of CHAPTER {detected_chapter}"
        elif detected_chapter == 6:
            msg = ">>> Detected Start of BIBLIOGRAPHY"
        elif detected_chapter == 7:
            msg = ">>> Detected Start of APPENDIX A"
        elif detected_chapter == 8:
            msg = ">>> Detected Start of APPENDIX B"
        elif detected_chapter == 9:
            msg = ">>> Detected Start of BIOGRAPHY"

        if msg:
            print(f"{u.CYAN}{u.BOLD}{msg} at Page {page.number + 1}{u.RST}")

    return detected_chapter