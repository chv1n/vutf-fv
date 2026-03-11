import os, io, csv, json, signal
from fastapi import FastAPI, UploadFile, File, Body, Path, HTTPException 
from pydantic import BaseModel
from fastapi.responses import StreamingResponse, JSONResponse
from config import OUTPUT_DIR, load_config, ANNOTATE
from urllib.parse import quote

# Import Validators
from core.validator import run_all_checks
from core.annotator import annotate_and_save_pdf

import uvicorn

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RST = '\033[0m'

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for local electron/vite dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LocalPDFRequest(BaseModel):
    file_path: str

def generate_csv(issues, summary=None):
    output = io.StringIO()
    writer = csv.writer(output)
    
    # เพิ่ม Header
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
    # ตัดนามสกุลเดิมออก (เช่น .pdf) แล้วเติม .csv
    base_name = os.path.splitext(original_filename)[0]
    csv_filename = f"{prefix}_{base_name}.csv"
    csv_path = os.path.join(OUTPUT_DIR, csv_filename)
    
    try:
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write(csv_content)
        print(f"{GREEN}Saved CSV report locally to: {csv_path}{RST}")
    except Exception as e:
        print(f"{RED}Failed to save CSV locally: {e}{RST}")

# ----------------------------------------------------------------------------------
# Endpoints สำหรับ API
# ----------------------------------------------------------------------------------
@app.post("/check_pdf")
async def check_pdf(file: UploadFile = File(...)):
    temp_in = f"temp_{file.filename}"
    local_out = os.path.join(OUTPUT_DIR, f"debug_{file.filename}")
    
    try:
        print("Receiving file:", file.filename)
        # 1. Save ไฟล์ Temp
        with open(temp_in, "wb") as f: f.write(await file.read())
        
        # 2. รันการตรวจสอบ
        issues = run_all_checks(temp_in)
        
        # 3. เช็ค Critical Error
        has_critical_error = any(i.code == "PAPER_SIZE_ERR" for i in issues)
    
        if not has_critical_error and ANNOTATE:
            print(f"{GREEN}Annotating PDF for {file.filename}...{RST}")
            annotate_and_save_pdf(temp_in, local_out, issues)
        else:
            print(f"Skipping annotation for {file.filename} due to critical paper size error.")
            
        # 4. สร้าง CSV Data
        csv_data = generate_csv(issues)
        
        # 5. บันทึกไฟล์ CSV ลงเครื่อง Server
        save_csv_to_disk(csv_data, file.filename, prefix="report_full")
        
        # 6. ส่งกลับ Client
        return StreamingResponse(
            io.StringIO(csv_data), 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('report.csv')}"}
        )
        
    except Exception as e: 
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(temp_in): os.remove(temp_in)

# ----------------------------------------------------------------------------------
# Endpoints สำหรับ Electron App
# ----------------------------------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "ok"}

@app.post("/check_local_pdf")
async def check_local_pdf(req: LocalPDFRequest):
    """ตรวจสอบ PDF จาก path ในเครื่อง (สำหรับ Electron app)"""
    file_path = req.file_path
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    try:
        issues = run_all_checks(file_path)
        
        # แปลง Issue object เป็น JSON-serializable format
        issues_json = [
            {
                "page": i.page,
                "code": i.code,
                "severity": i.severity,
                "message": i.message,
                "bbox": list(i.bbox) if i.bbox else None
            }
            for i in issues
        ]

        # ถ้ามี PAPER_SIZE_ERR จะไม่ตรวจต่อ
        if any(i.code == "PAPER_SIZE_ERR" for i in issues):
            return JSONResponse(status_code=400, content={"error": "ขนาดกระดาษไม่ถูกต้อง", "data": issues_json})
        
        return {"issues": issues_json, "data": issues_json}
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/shutdown")
def shutdown():
    """Graceful shutdown สำหรับ Electron app ปิด backend ตอนจบโปรแกรม"""
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "shutting down"}

@app.get("/config")
def get_config():
    new_config = load_config()
    return new_config

@app.put("/config/update")
async def update_config(new_data: dict = Body(...)):
    try:
        temp_file = "config.json.tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4, ensure_ascii=False)

        os.replace(temp_file, "config.json")

        return {"status": "success", "message": "Config updated"}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__": uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)