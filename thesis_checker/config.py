import json
import os

CONFIG_FILE = "config.json"
OUTPUT_DIR = "output_files"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

DEFAULT_CONFIG = load_config() 

ANNOTATE = True

DEBUG = True
DEBUG_LINE = False

THAI_SEQ = "กขคงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"
PATTERNS = {
    "chapter": r"^(บทที่\s+\d+)",
    "image_table": r"^((?:รูปที่|ตารางที่)\s*[0-9๐-๙]+(?:\.[0-9๐-๙]+)*)",
    "invalid_heading": r"^(\d+\.\d+\.\d+\.\d+(?:\.\d+)*)(\s|(?=[^\s])|$)", 
    "sub_section": r"^(\d+\.\d+\.\d+)(?!\.)(\s|(?=[^\s])|$)",
    "section": r"^(\d+\.\d+)(?!\.)(\s|(?=[^\s])|$)",
    "sub_sub_section": r"^\s*((\d+|[๑-๙][๐-๙]*)\s*\))(\s|$)",
    "bullet": r"^([•\u2022])",
    "dash": r"^([-–—])"
}
WARNING_FONTS = ["cordia", "angsana", "browallia", "upc"]
IGNORED_SYMBOLS = ["•", "●", "▪", "-", "–", "—", "_"]
MATH_FONTS = ["math", "symbol", "cambria", "mt", "wingdings", "times"]
NUMERIC_PATTERN = r"^[0-9\[\]\(\)\.,\-\+\*/=]+$"
LATIN_VAR_PATTERN = r"^[A-Za-z0-9\.\-\s]{1,5}$"
GREEK_SYMBOLS = ["∑", "Σ", "µ", "β", "Ω", "π", "∆", "ε", "σ", "τ", "φ", "θ", "ρ", "χ", "ψ", "ω", "κ", "λ", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ", "λ", "μ", "ν", "ξ", "π", "τ", "υ", "φ", "χ", "ψ", "ω", "α"]
NO_PAGE_SECTIONS = {1, 2, 3, 4, 5, 7, 8, 9, 10, 11}