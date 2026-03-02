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
            
    print("Warning: config.json not found or error. Using default config.")
    
    return {
        "margin_mm": {"top": 38.1, "bottom": 25.4, "left": 38.1, "right": 25.4},
        
        "font": {
            "name": "sarabun",
            "size": 16.0,
            "tolerance": 1.0
        },
        
        "indent_rules": {
            "tolerance": 2.0,
            
            "para_indent": 10.0, 
            "para_min_detect": 5.0,
            "para_max_detect": 35.0,

            "main_heading_num": 0.0,
            "main_heading_text": 10.0,

            "sub_heading_num": 10.0,
            "sub_heading_text_1": 20.0,
            "sub_heading_text_2": 22.5,

            "list_item_num": 15.0,
            "list_item_text_1": 25.0,
            "list_item_text_2": 27.6,

            "bullet_point": 25.0,
            "bullet_text": 30.0
        },
        
        "check_list": {
            "check_font": True, 
            "check_margin": True, 
            "check_section_seq": True,
            "check_page_seq": True,     
            "check_indentation": True, 
            "check_spacing": False,
            "check_paper_size": False
        },
        
        "ignored_units": [
            "m", "cm", "mm", "km", "nm",
            "kg", "g", "mg",
            "A", "mA", "kA",
            "V", "kV", "mV",
            "W", "kW", "MW",
            "Hz", "kHz", "MHz", "GHz",
            "J", "MJ", "kJ",
            "°C", "K", "F",
            "N", "kN",
            "Pa", "kPa", "MPa",
            "bar", "atm",
            "dB", "rpm"
        ]
    }

DEFAULT_CONFIG = load_config() 
DEBUG = True
THAI_SEQ = "กขคงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"