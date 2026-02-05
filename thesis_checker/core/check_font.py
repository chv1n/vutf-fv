import re
from typing import List
from models import Issue

def check_font(page_num: int, spans: list, font_cfg: dict) -> List[Issue]:
    """
    ตรวจสอบกฎเกี่ยวกับฟอนต์ (ชื่อและขนาด)
    โดยข้าม Bullet, ตัวยก/ตัวห้อย, สมการคณิตศาสตร์, และตัวแปรภาษาอังกฤษ (Variable)
    """
    found_issues = []
    
    # ดึงค่า Config
    font_keyword = font_cfg.get("name", "sarabun").lower()
    font_size_target = font_cfg.get("size", 16.0)
    font_tol = font_cfg.get("tolerance", 0.5)

    # 1. ฟอนต์ไทยที่อนุโลมให้เป็น Warning
    WARNING_FONTS = ["cordia", "angsana", "browallia", "upc"]

    # 2. สัญลักษณ์ที่ยกเว้น
    IGNORED_SYMBOLS = ["•", "●", "▪", "-", "–", "—", "_"]
    
    # 3. ฟอนต์คณิตศาสตร์/สัญลักษณ์ (Whitelist)
    MATH_FONTS = ["math", "symbol", "cambria", "mt", "wingdings", "times"]
    
    # 4. Regex Patterns
    # - ตัวเลขและสัญลักษณ์พื้นฐาน
    NUMERIC_PATTERN = r"^[0-9\[\]\(\)\.,\-\+\*/=]+$"
    # - [NEW] ตัวแปรภาษาอังกฤษสั้นๆ (เช่น N, x, y, CH, S.D., pH) ไม่เกิน 5 ตัวอักษร
    #   (ป้องกันไม่ให้ข้ามประโยคภาษาอังกฤษยาวๆ ที่ควรตรวจ)
    LATIN_VAR_PATTERN = r"^[A-Za-z0-9\.\-\s]{1,5}$"

    # [NEW] รายการสัญลักษณ์กรีกที่พบบ่อย (Sigma, Mu, etc.)
    GREEK_SYMBOLS = ["∑", "Σ", "µ", "μ", "α", "β", "Ω", "π", "∆"]

    for span in spans:
        text_content = span["text"].strip()
        span_size = span["size"]
        f_name_lower = span["font"].lower()

        # --- Filter 1: ข้ามถ้าว่างเปล่า ---
        if not text_content: continue
        
        # --- Filter 2: ข้าม Bullet Points ---
        if text_content in IGNORED_SYMBOLS: continue

        # --- Filter 3: ข้ามฟอนต์คณิตศาสตร์ ---
        if any(m in f_name_lower for m in MATH_FONTS):
            continue

        # --- Filter 4: ข้ามสัญลักษณ์กรีก (Greek Symbols) ---
        if any(g in text_content for g in GREEK_SYMBOLS):
            continue

        # --- Filter 5: ข้ามตัวเลข/ตัวแปร (Variables & Formulas) ---
        # กรณีที่ 1: เป็นตัวเลขล้วนๆ
        if re.match(NUMERIC_PATTERN, text_content):
            # ถ้าขนาดเล็ก (ตัวยก/ห้อย) หรืออยู่ในสมการ ให้ข้าม
            if span_size < (font_size_target - 1.0): 
                continue

        # กรณีที่ 2: เป็นตัวอักษรภาษาอังกฤษสั้นๆ (Variables / Chemical)
        # เช่น "N", "X", "CH", "S.D."
        if re.match(LATIN_VAR_PATTERN, text_content):
            # อนุมานว่าภาษาอังกฤษสั้นๆ ที่ขนาดเพี้ยนหรือฟอนต์ไม่ตรง คือตัวแปรในสมการ
            continue
        
        # 1. ตรวจชื่อฟอนต์
        if font_keyword not in f_name_lower and "cidfont" not in f_name_lower and "cordia" not in f_name_lower:
            
            if any(wf in f_name_lower for wf in WARNING_FONTS):
                severity = "warning"
                msg = f"ฟอนต์ภายในเป็น {span['font']} (อนุโลม)"
            else:
                severity = "error"
                msg = f"ฟอนต์ผิดระเบียบ: {span['font']} (ต้องเป็น Sarabun)"

            found_issues.append(Issue(
                page=page_num, 
                code="FONT_NAME", 
                severity=severity, 
                message=msg, 
                bbox=span["bbox"]
            ))
        
        # 2. ตรวจขนาดฟอนต์
        # เช็คเฉพาะฟอนต์ขนาดปกติ (10-20pt) เพื่อไม่ให้ไปกวนพวก Header ใหญ่ๆ
        if 10.0 <= span_size <= 20.0:
            if abs(span_size - font_size_target) > font_tol:
                found_issues.append(Issue(
                    page=page_num, 
                    code="FONT_SIZE", 
                    severity="error", 
                    message=f"ขนาดผิด: {span_size:.1f}pt (เจอ '{text_content}')", 
                    bbox=span["bbox"]
                ))
                
    return found_issues