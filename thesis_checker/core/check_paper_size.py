import fitz
from typing import List
from models import Issue

def check_paper_size(doc: fitz.Document) -> List[Issue]:
    """
    Check if all pages are A4 size (approx 595 x 842 points).
    Returns a list of Critical Issues if any page is not A4.
    """
    issues = []
    
    # Standard A4 constants
    A4_W, A4_H = 595.0, 842.0
    TOLERANCE = 5.0
    
    # Factor สำหรับแปลง Point -> Millimeter (1 pt = 1/72 inch, 1 inch = 25.4 mm)
    PT_TO_MM = 25.4 / 72

    print("=== Pre-check: Validating Paper Size (A4) ===")

    for i, page in enumerate(doc, 1):
        w = page.rect.width
        h = page.rect.height
        
        # Check logic: Must be close to A4 dimensions (Portrait)
        is_width_ok = abs(w - A4_W) < TOLERANCE
        is_height_ok = abs(h - A4_H) < TOLERANCE
        
        if not (is_width_ok and is_height_ok):
            # แปลงเป็น mm เพื่อให้ User เข้าใจง่ายขึ้น
            w_mm = w * PT_TO_MM
            h_mm = h * PT_TO_MM
            
            # ปรับข้อความให้ชัดเจน: บอกทั้งหน่วย pt และ mm
            msg = (
                f"ขนาดกระดาษผิด: พบขนาด {w:.1f}x{h:.1f} pt ({w_mm:.1f}x{h_mm:.1f} มม.) "
                f"| มาตรฐาน A4 ต้องเป็น ~595x842 pt (210x297 มม.)"
            )
        
            # print(f"Page {i} ERROR: Found {w:.1f}x{h:.1f} pt ({w_mm:.1f}x{h_mm:.1f} mm)")
            
            issues.append(Issue(
                page=i, 
                code="PAPER_SIZE_ERR", 
                severity="critical", 
                message=msg, 
                bbox=[0, 0, w, h]
            ))
        # (Optional) ถ้าอยากให้ Print หน้าที่ผ่านด้วยให้เปิดบรรทัดนี้
        # else:
        #     print(f"  ✅ Page {i} OK")

    return issues