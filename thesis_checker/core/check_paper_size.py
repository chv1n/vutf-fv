import fitz
from typing import List
from models import Issue

def check_paper_size(doc: fitz.Document) -> List[Issue]:
    """
    Check if all pages are A4 size (approx 595 x 842 points).
    Returns a list of Critical Issues if any page is not A4.
    """
    issues = []
    
    A4_SHORT = 595.0
    A4_LONG = 842.0
    TOLERANCE = 25.0
    PT_TO_MM = 25.4 / 72

    for i, page in enumerate(doc, 1):
        w = page.rect.width
        h = page.rect.height
        
        side_min = min(w, h)
        side_max = max(w, h)
        
        is_short_ok = abs(side_min - A4_SHORT) < TOLERANCE
        is_long_ok = abs(side_max - A4_LONG) < TOLERANCE
        
        if not (is_short_ok and is_long_ok):
            w_mm = w * PT_TO_MM
            h_mm = h * PT_TO_MM
            
            msg = (
                f"ขนาดกระดาษผิด: พบขนาด {w:.1f}x{h:.1f} pt ({w_mm:.1f}x{h_mm:.1f} มม.) "
                f"| มาตรฐาน A4 ต้องเป็น 595x842 pt (210x297 มม.)"
            )
            issues.append(Issue(
                page=i, 
                code="PAPER_SIZE_ERR", 
                severity="error", 
                message=msg, 
                bbox=[0, 0, w, h]
            ))

    return issues