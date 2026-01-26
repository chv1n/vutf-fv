import fitz

def get_page_number_text(page: fitz.Page, margin_top: float) -> str:
    """
    ดึงข้อความจากมุมขวาบนของหน้า (Header Zone) ที่คาดว่าเป็นเลขหน้า
    
    :param page: fitz.Page object
    :param margin_top: ระยะขอบบน (หน่วย point) เพื่อกำหนดความสูงของโซนค้นหา
    :return: ข้อความที่เจอ (String) ถ้าไม่เจอคืนค่าว่าง
    """
    w = page.rect.width
    
    # กำหนดโซนค้นหา: 
    # - แนวนอน: เอา 30% ทางขวาสุด (w * 0.7 ถึง w)
    # - แนวตั้ง: จากขอบบนสุด ถึงระยะ Margin Top (คูณ 0.9 เพื่อกันไปโดนเนื้อหาบรรทัดแรก)
    header_rect = fitz.Rect(w * 0.7, 0, w, margin_top * 0.9)
    
    # ดึงข้อความในกรอบ
    # flags=0 หรือ sort=True จะช่วยให้อ่านตามลำดับบรรทัดได้ดีขึ้น (แต่เลขหน้ามักมีบรรทัดเดียว)
    raw_text = page.get_text("text", clip=header_rect).strip()
    
    # ลบพวก Newline (\n) ที่อาจติดมาทิ้งไป
    clean_text = raw_text.replace('\n', '').strip()
    
    return clean_text