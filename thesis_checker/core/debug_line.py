import  re
from    typing import List, Tuple, Optional
from    core.check_utils import extract_prefix_and_text_bboxes
from    config import PATTERNS

RED = '\033[91m'
GREEN = '\033[92m'
BLUE = '\033[94m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
MAGENTA = '\033[95m'
RST = '\033[0m'

def debug_classify_block(line: str) -> dict:
    """
    รับบรรทัดข้อความมา จัดประเภท และแยก prefix ออกจากข้อความ
    """

    original_line = line

    if not line or not line.strip():
        return {"type": "EMPTY", "prefix": "", "text": ""}

    line = line.lstrip()

    for line_type, regex in PATTERNS.items():

        match = re.search(regex, line)

        if not match:
            continue

        prefix = match.group(1)

        # แยก text หลัง prefix
        text = line[match.end(1):].strip()

        # รูป / ตาราง
        if line_type == "image_table_caption":
            if prefix.startswith("รูปที่"):
                line_type = "image_caption"
            else:
                line_type = "table_caption"

        return {
            "type": line_type,
            "prefix": prefix,
            "text": text
        }

    return {
        "type": "paragraph",
        "prefix": "",
        "text": original_line.strip()
    }

def debug_line(page_num: int, line_text: str, line_dict: dict, chapter_num: int):
    page_header = ""
    if getattr(debug_line, "last_page", None) != page_num:

        page_header = f"\n================== PAGE {page_num} ==================\n"
        debug_line.last_page = page_num

    result = debug_classify_block(line_text)

    line_type = result['type']
    prefix = result['prefix']
    text = result['text']

    color = RST
    if line_type == "chapter":
        color = GREEN
    elif line_type == "section":
        color = BLUE
    elif line_type == "sub_section":
        color = CYAN
    elif line_type == "sub_sub_section":
        color = YELLOW
    elif line_type in ["image", "table"]:
        color = MAGENTA
    elif line_type == "bullet":
        color = RED
    elif line_type == "paragraph":
        color = RST

    if prefix:
        p_bbox, t_bbox = extract_prefix_and_text_bboxes(line_dict, prefix)
        p_str = f"[{p_bbox[0]:.1f}, {p_bbox[1]:.1f}, {p_bbox[2]:.1f}, {p_bbox[3]:.1f}]" if p_bbox else "None"
        t_str = f"[{t_bbox[0]:.1f}, {t_bbox[1]:.1f}, {t_bbox[2]:.1f}, {t_bbox[3]:.1f}]" if t_bbox else "None"
        debug_str = f"[{color}{line_type}{RST}] PREFIX {p_str}: '{color}{prefix}{RST}' | TEXT {t_str}: '{text}'"
    else:
        t_bbox = line_dict.get("bbox")
        t_str = f"[{t_bbox[0]:.1f}, {t_bbox[1]:.1f}, {t_bbox[2]:.1f}, {t_bbox[3]:.1f}]" if t_bbox else "None"
        debug_str = f"[{color}{line_type}{RST}] TEXT {t_str}: '{text}'"

    return page_header + debug_str