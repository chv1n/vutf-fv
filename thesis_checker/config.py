import json
import os

CONFIG_FILE = "config.json"
OUTPUT_DIR = "output_files"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON: {e}")
            
    print("Warning: config.json not found or error.")
    
    return {
        # ตั้งค่า Margin ตามคู่มือ
        "margin_mm": {"top": 38.1, "bottom": 25.4, "left": 38.1, "right": 25.4},
        
        "font": {
            "name": "sarabun",
            "size": 16.0,       # [แก้] ตามคู่มือระบุ 16 pt [cite: 52]
            "tolerance": 0.5
        },
        
        # --- กำหนดระยะเยื้อง (Indentation) ---
        "indent_rules": {
            "paragraph": 15.0,           # ย่อหน้าปกติ (มักจะเริ่มที่ 1.5 ซม. หรือ 1.0 ซม. แล้วแต่คณะ)
            
            # หัวข้อระดับ 3 (เช่น 1) )
            "sub_section_num": 15.0,     # [แก้] ตามคู่มือระบุ 1.5 ซม. 
            "sub_section_text_1": 25.0,  # ถูกต้อง (2.5 ซม. สำหรับเลข 1 หลัก) [cite: 70]
            "sub_section_text_2": 27.6,  # ถูกต้อง (2.76 ซม. สำหรับเลข 2 หลัก) [cite: 72]
            
            # หัวข้อระดับ 4 (Bullet •)
            "bullet_point": 25.0,        # ถูกต้อง (2.5 ซม.) [cite: 73]
            "bullet_text": 30.0,         # ถูกต้อง (3.0 ซม.) [cite: 73]
            
            "tolerance": 2.0             # ยอมให้คลาดเคลื่อน 2 มม.
        },
        
        "check_list": {
            "check_font": True, 
            "check_margin": True, 
            "check_section_seq": True,
            "check_page_seq": False,     
            "check_indentation": True, 
            "check_spacing": False 
        }
    }

DEFAULT_CONFIG = load_config() 
DEBUG = True
THAI_SEQ = "กขคงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"