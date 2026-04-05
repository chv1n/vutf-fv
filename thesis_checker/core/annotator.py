import fitz
from typing import List
from models import Issue
from tqdm import tqdm

def annotate_and_save_pdf(input_path: str, output_path: str, issues: List[Issue]):
    print(f"[Annotator] Opening PDF: {input_path}")
    doc = fitz.open(input_path)
    
    for i, page in enumerate(tqdm(doc, desc="Annotating PDF", unit="page"), 1):
        page_issues = [x for x in issues if x.page == i]
        
        for issue in page_issues:
            color = (1, 0, 0) if issue.severity == "error" else (1, 0.6, 0)
            
            if issue.bbox:
                r = fitz.Rect(issue.bbox)
                
                if r.is_empty or r.is_infinite or r.width <= 0 or r.height <= 0:
                    continue
                
                annot = page.add_rect_annot(r)
                annot.set_border(width=0.5)  
                annot.set_colors(stroke=color)
                
                annot.set_info(content=issue.message, title="Thesis Checker", subject=issue.code) 
                annot.update()

                text_point = fitz.Point(r.x0, r.y0 - 2)
                
                if r.y0 < 15:
                    text_point = fitz.Point(r.x0, r.y1 + 8)

                page.insert_text(
                    text_point,
                    str(issue.code), 
                    fontsize=8,  
                    fontname="helv", 
                    color=color       
                )

    print(f"[Annotator] Saving annotated PDF to: {output_path}")
    doc.save(output_path, garbage=4, deflate=True) 
    doc.close()