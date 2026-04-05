import fitz
import re
import utils as u

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RST = '\033[0m'

def detect_current_chapter(page: fitz.Page, current_chapter_num: int) -> int:
    """
    ระบุส่วนต่างๆ ของเล่ม (1-9)
    โดยมีการกรองหน้า "สารบัญ" และ "หน้าที่มีเลข ก-ฮ" ออก
    """
    w = page.rect.width
    h = page.rect.height

    header_zone = fitz.Rect(0, 0, w, h * 0.2)
    header_text = page.get_text("text", clip=header_zone).strip()

    center_zone = fitz.Rect(0, h * 0.3, w, h * 0.7)
    center_text = page.get_text("text", clip=center_zone).strip()

    footer_zone = fitz.Rect(0, h * 0.8, w, h)
    footer_text = page.get_text("text", clip=footer_zone).strip()
    
    page_num_rect = fitz.Rect(w * 0.7, 0, w, h * 0.1) 
    page_num_text = page.get_text("text", clip=page_num_rect).strip()

    # กรองหน้าสารบัญ (Keywords)
    if "สารบัญ" in header_text and len(header_text.strip()) <= 50:
        return current_chapter_num

    # กรองเลขหน้าไทย
    if re.search(r"^[ก-ฮ]{1,3}$", page_num_text):
        return 0 # หรือ return current_chapter_num

    # เพิ่มการเช็คใน header_text ด้วย
    lines = header_text.split('\n')
    for line in lines:
        if re.match(r"^\s*[ก-ฮ]{1,3}\s*$", line):
             return 0 # เจอเลขหน้าไทย -> บังคับเป็น Pre-content

    detected_chapter = current_chapter_num

    # ตรวจหา "บทที่ 1-5" (เช็ค Header)
    match_chapter = re.search(r"บทที่\s*(\d+)", header_text)
    if match_chapter:
        try:
            found_num = int(match_chapter.group(1))
            if 1 <= found_num <= 5:
                detected_chapter = found_num
        except ValueError:
            pass

    # ตรวจหา ส่วนท้ายเล่ม 
    elif "บรรณานุกรม" in header_text:
        detected_chapter = 6
    elif "ภาคผนวก ก" in center_text and len(center_text.strip()) <= 50:
        detected_chapter = 7 
    elif "ภาคผนวก ข" in center_text and len(center_text.strip()) <= 50:
        detected_chapter = 8
    elif "ภาคผนวก ค" in center_text and len(center_text.strip()) <= 50:
        detected_chapter = 9
    elif "ภาคผนวก ง" in center_text and len(center_text.strip()) <= 50:
        detected_chapter = 10
    elif "ประวัติผู้จัดทำ" in header_text or "ประวัติผู้จัดทำ" in center_text:
        detected_chapter = 11

    # Print Debug (เฉพาะตอนเปลี่ยนบท)
    # if detected_chapter != current_chapter_num:
    #     msg = ""
    #     if 1 <= detected_chapter <= 5:
    #         msg = f">>> Detected Start of CHAPTER {detected_chapter}"
    #     elif detected_chapter == 6:
    #         msg = ">>> Detected Start of BIBLIOGRAPHY (บรรณานุกรม)"
    #     elif detected_chapter == 7:
    #         msg = ">>> Detected Start of APPENDIX A (ภาคผนวก ก)"
    #     elif detected_chapter == 8:
    #         msg = ">>> Detected Start of APPENDIX B (ภาคผนวก ข)"
    #     elif detected_chapter == 9:
    #         msg = ">>> Detected Start of APPENDIX C (ภาคผนวก ค)"
    #     elif detected_chapter == 10:
    #         msg = ">>> Detected Start of BIOGRAPHY (ประวัติผู้จัดทำ)"

    #     if msg:
    #         print(f"{u.CYAN}{u.BOLD}{msg} at Page {page.number + 1}{u.RST}")

    return detected_chapter