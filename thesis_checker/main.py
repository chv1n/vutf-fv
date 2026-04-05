import os, io, csv, json
from fastapi import FastAPI, UploadFile, File, Body, Path, HTTPException 
from fastapi.responses import StreamingResponse, JSONResponse
from config import OUTPUT_DIR, DEFAULT_CONFIG, load_config
from urllib.parse import quote

# Import Validators
from core.validator import run_all_checks
from core.annotator import annotate_and_save_pdf

import uvicorn

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RST = '\033[0m'
RST = '\033[0m'

app = FastAPI()

ANNOTATE = True

def generate_csv(issues, summary=None):
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Page", "Code", "Severity", "Message", "BBox"])
    
    for i in issues:
        bbox_str = ""
        if i.bbox:
            rounded_bbox = [round(x, 2) for x in i.bbox]
            bbox_str = str(rounded_bbox)

        writer.writerow([i.page, i.code, i.severity, i.message, bbox_str])
        
    return output.getvalue()

# บันทึก CSV ลงเครื่อง
def save_csv_to_disk(csv_content: str, original_filename: str, prefix: str = "report"):
    base_name = os.path.splitext(original_filename)[0]
    csv_filename = f"{prefix}_{base_name}.csv"
    csv_path = os.path.join(OUTPUT_DIR, csv_filename)
    
    try:
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write(csv_content)
        print(f"{GREEN}Saved CSV report locally to: {csv_path}{RST}")
    except Exception as e:
        print(f"{RED}Failed to save CSV locally: {e}{RST}")

@app.post("/check_pdf")
async def check_pdf(file: UploadFile = File(...)):
    temp_in = f"temp_{file.filename}"
    local_out = os.path.join(OUTPUT_DIR, f"debug_{file.filename}")
    
    try:
        print("Receiving file:", file.filename)
        with open(temp_in, "wb") as f: f.write(await file.read())
        issues = run_all_checks(temp_in)
        has_critical_error = any(i.code == "PAPER_SIZE_ERR" for i in issues)
    
        if not has_critical_error and ANNOTATE:
            print(f"{GREEN}Annotating PDF for {file.filename}...{RST}")
            annotate_and_save_pdf(temp_in, local_out, issues)
        else:
            print(f"Skipping annotation for {file.filename} due to critical paper size error.")
            
        csv_data = generate_csv(issues)
        
        save_csv_to_disk(csv_data, file.filename, prefix="report_full")

        return StreamingResponse(
            io.StringIO(csv_data), 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('report.csv')}"}
        )
        
    except Exception as e: 
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(temp_in): os.remove(temp_in)

@app.get("/config")
def get_config():
    new_config = load_config()
    return new_config

@app.put("/config/update")
async def update_config(new_data: dict = Body(...)):
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4, ensure_ascii=False)
        from config import load_config
        global DEFAULT_CONFIG
        DEFAULT_CONFIG = load_config()
        return {"status": "success", "message": "Config updated and saved to file"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__": uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)