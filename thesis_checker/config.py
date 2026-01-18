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
            
    print("Warning: config.json not found or error. Using hardcoded defaults.")
    return {
        "margin_mm": {"top": 38.1, "bottom": 25.4, "left": 38.1, "right": 25.4},
        "font": {"name": "sarabun", "size": 16.0, "tolerance": 0.5},
        "indent_rules": {
            "paragraph": 15.0,
            "sub_section_num": 15.0,
            "sub_section_text_1": 25.0,
            "sub_section_text_2": 27.6,
            "bullet_point": 25.0,
            "bullet_text": 30.0,
            "tolerance": 1.0
        },
        "CHECK_LIST": {
            "check_font": True, 
            "check_margin": True, 
            "check_section_seq": True,
            "check_page_seq": True, 
            "check_indentation": True, 
            "check_spacing": True
        }
    }

DEFAULT_CONFIG = load_config() 
DEBUG = 1
THAI_SEQ = "กขคงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"