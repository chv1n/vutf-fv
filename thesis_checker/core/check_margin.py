from typing import List
from models import Issue
from utils import mm

def check_margin_rules(page_num: int, bbox: list, margin_cfg: dict) -> List[Issue]:
    """
    ตรวจสอบว่าข้อความล้นขอบกระดาษหรือไม่
    :param page_num: เลขหน้า
    :param bbox: กรอบข้อความ [x0, y0, x1, y1]
    :param margin_cfg: ค่า Config ของ Margin (เช่น {"top": 25.4, "left": 38.1, ...})
    """
    issues = []
    
    # แปลงค่า Config จากนิ้ว/อื่นๆ เป็น Point (หรือ mm ตาม utils)
    # ในที่นี้สมมติว่า utils.mm แปลงค่าเป็นหน่วยเดียวกับ bbox (pdf points)
    m_left = mm(margin_cfg.get("left", 38.1)) 
    
    # x0 คือตำแหน่งซ้ายสุดของกล่องข้อความ
    x0 = bbox[0]
    
    # ตรวจสอบขอบซ้าย (อนุโลมให้ 1.0 point/mm ตามโค้ดเดิม)
    if x0 < (m_left - 1.0):
        issues.append(Issue(
            page=page_num, 
            code="MARGIN_LEFT", 
            severity="error", # หรือ warning แล้วแต่กำหนด
            message="ล้นขอบซ้าย", 
            bbox=bbox
        ))
        
    # อนาคตสามารถเพิ่มการตรวจขอบขวา (Right Margin) ได้ที่นี่
    # m_right = ...
    # if x1 > ...
    
    return issues