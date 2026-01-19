import fitz
import re
import utils as u

def detect_current_chapter(page: fitz.Page, current_chapter_num: int) -> int:
    """
    ระบุส่วนต่างๆ ของเล่มโครงงาน (1-9) โดยตรวจจับทั้งส่วนหัวและกึ่งกลางหน้า
    
    State Definition:
    - 0: Pre-content
    - 1-5: บทที่ 1 ถึง 5
    - 6: บรรณานุกรม (Bibliography)
    - 7: ภาคผนวก ก (Appendix A - คู่มือการใช้งาน)
    - 8: ภาคผนวก ข (Appendix B - Source Code)
    - 9: ประวัติผู้จัดทำ (Biography)
    """
    
    w = page.rect.width
    h = page.rect.height
    
    # 1. โซนตรวจจับส่วนหัวหน้า (25% ด้านบน)
    header_zone = fitz.Rect(0, 0, w, h * 0.25)
    header_text = page.get_text("text", clip=header_zone).strip()
    
    # 2. โซนตรวจจับกึ่งกลางหน้า (สำหรับหน้าคั่นภาคผนวกและประวัติ)
    center_zone = fitz.Rect(0, h * 0.3, w, h * 0.7)
    center_text = page.get_text("text", clip=center_zone).strip()
    
    # 3. ข้อความทั้งหน้า (Full page text) เพื่อความแม่นยำสูงสุด
    full_text = page.get_text("text").strip()
    
    detected_chapter = current_chapter_num

    # ---------------------------------------------------------
    # Logic 1: ตรวจหา "บทที่ 1-5"
    # ---------------------------------------------------------
    # ใช้ full_text เพราะหน้าแรกของบทมักวางหัวข้อไว้ต่ำกว่า Header ปกติ
    match_chapter = re.search(r"บทที่\s*(\d+)", full_text)
    if match_chapter:
        try:
            found_num = int(match_chapter.group(1))
            if 1 <= found_num <= 5:
                detected_chapter = found_num
        except ValueError:
            pass

    # ---------------------------------------------------------
    # Logic 2-5: ตรวจหา ส่วนท้ายเล่ม (ใช้ Keywords)
    # ---------------------------------------------------------
    # บรรณานุกรม
    elif "บรรณานุกรม" in header_text:
        detected_chapter = 6
    
    # ภาคผนวก ก: เช็คกึ่งกลางหน้า (หน้าคั่น)
    elif "ภาคผนวก ก" in center_text or "ภาคผนวก ก" in header_text:
        detected_chapter = 7
        
    # ภาคผนวก ข: เช็คกึ่งกลางหน้า (หน้าคั่น)
    elif "ภาคผนวก ข" in center_text or "ภาคผนวก ข" in header_text:
        detected_chapter = 8
        
    # ประวัติผู้จัดทำ: เช็คจากเนื้อหาทั้งหน้า
    elif "ประวัติผู้จัดทำ" in full_text:
        detected_chapter = 9

    # ---------------------------------------------------------
    # แจ้งเตือนเมื่อมีการเปลี่ยนสถานะ (Print Statements)
    # ---------------------------------------------------------
    if detected_chapter != current_chapter_num:
        msg = ""
        if 1 <= detected_chapter <= 5:
            msg = f">>> Detected Start of CHAPTER {detected_chapter}"
        elif detected_chapter == 6:
            msg = ">>> Detected Start of BIBLIOGRAPHY"
        elif detected_chapter == 7:
            msg = ">>> Detected Start of APPENDIX A (Manual)" #
        elif detected_chapter == 8:
            msg = ">>> Detected Start of APPENDIX B (Source Code)" #
        elif detected_chapter == 9:
            msg = ">>> Detected Start of BIOGRAPHY" #

        if msg:
            print(f"{u.CYAN}{u.BOLD}{msg} at Page {page.number + 1}{u.RST}")

    return detected_chapter