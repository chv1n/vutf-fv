import os, io, csv, json
from fastapi import FastAPI, UploadFile, File, Body, Path, HTTPException 
from fastapi.responses import StreamingResponse, JSONResponse
from config import OUTPUT_DIR, DEFAULT_CONFIG, load_config
from urllib.parse import quote
from config import OUTPUT_DIR, DEFAULT_CONFIG, load_config
from urllib.parse import quote

from core.chapter1_validator import check_chapter_1
from core.chapter2_validator import check_chapter_2

from core.chapter_validator import validate_chapter
import uvicorn

from config import OUTPUT_DIR
from core.validator import run_all_checks
from core.chapter1_validator import check_chapter_1

from core.annotator import annotate_and_save_pdf

app = FastAPI()

ANNOTATE = False

def generate_csv(issues, summary=None):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Page", "Code", "Severity", "Message", "BBox"])
    for i in issues: writer.writerow([i.page, i.code, i.severity, i.message, str(i.bbox)])
    return output.getvalue()

# -------------------------------------------------------------------------------------------------------
@app.post("/check_pdf")
async def check_pdf(file: UploadFile = File(...)):
    temp_in = f"temp_{file.filename}"
    local_out = os.path.join(OUTPUT_DIR, f"debug_{file.filename}")
    
    try:
        # 1. Save ไฟล์ Temp
        with open(temp_in, "wb") as f: f.write(await file.read())
        # 2. รันการตรวจสอบ
        issues = run_all_checks(temp_in)
        # 3. [เพิ่ม Logic ตรงนี้] เช็คว่ามี Critical Error (ขนาดกระดาษผิด) หรือไม่
        # ถ้ามี PAPER_SIZE_ERR ให้ข้ามการ Annotate
        has_critical_error = any(i.code == "PAPER_SIZE_ERR" for i in issues)
    
        if not has_critical_error and ANNOTATE:
            # ถ้าไม่มี Error ร้ายแรง ค่อยวาดกรอบแดง
            annotate_and_save_pdf(temp_in, local_out, issues)
        else:
            print(f"Skipping annotation for {file.filename} due to critical paper size error.")
            
        # 4. สร้าง CSV (ยังคงสร้าง CSV ส่งกลับไปเพื่อให้ User รู้ว่าผิดตรงไหน)
        csv_data = generate_csv(issues)
        
        return StreamingResponse(
            io.StringIO(csv_data), 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('report.csv')}"}
        )
        
    except Exception as e: 
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(temp_in): os.remove(temp_in)
# -------------------------------------------------------------------------------------------------------

@app.post("/check_chapter/{chapter_num}")
async def check_specific_chapter(
    # รับค่าจาก URL และตรวจสอบว่าต้องเป็น 1-5 เท่านั้น
    chapter_num: int = Path(..., title="The chapter number to validate", ge=1, le=5),
    file: UploadFile = File(...) 
):
    """
    ตรวจไฟล์ PDF ตามบทที่ระบุใน URL 
    ตัวอย่าง: POST /check_chapter/1
    """
    
    # ตั้งชื่อไฟล์ Temp
    temp_in = f"temp_chap{chapter_num}_{file.filename}"
    local_out = os.path.join(OUTPUT_DIR, f"debug_chap{chapter_num}_{file.filename}")
    
    try:
        # 1. Save ไฟล์
        with open(temp_in, "wb") as f: f.write(await file.read())
        
        # 2. เรียกฟังก์ชัน Validate (ส่งเลขบทเข้าไป)
        issues = validate_chapter(temp_in, chapter_num=chapter_num)
        
        # 3. วาดกรอบ Error
        annotate_and_save_pdf(temp_in, local_out, issues)
        
        # 4. ส่งกลับเป็น CSV
        csv_data = generate_csv(issues)
        report_filename = f"report_chapter{chapter_num}.csv"
        
        return StreamingResponse(
            io.StringIO(csv_data), 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(report_filename)}"}
        )
        
    except Exception as e: 
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(temp_in): os.remove(temp_in)

@app.post("/check_chapter1")
async def check_chapter1(file: UploadFile = File(...)):
    temp_in = f"temp_{file.filename}"
    local_out = os.path.join(OUTPUT_DIR, f"debug_chap1_{file.filename}")
    try:
        with open(temp_in, "wb") as f: f.write(await file.read())
        
        # ฟังก์ชัน check_chapter_1 เราเขียนไว้ให้คืนค่าแค่ issues (ไม่มี summary)
        issues = check_chapter_1(temp_in)
        
        annotate_and_save_pdf(temp_in, local_out, issues)
        
        # ส่งแค่ issues (summary เป็น None)
        csv_data = generate_csv(issues, summary=None) 
        
        return StreamingResponse(
            io.StringIO(csv_data), 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('report_chapter1.csv')}"}
        )
    except Exception as e: 
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(temp_in): os.remove(temp_in)


@app.post("/check_chapter2")
async def check_chapter2(file: UploadFile = File(...)):
    temp_in = f"temp_{file.filename}"
    local_out = os.path.join(OUTPUT_DIR, f"debug_chap2_{file.filename}")
    try:
        with open(temp_in, "wb") as f: f.write(await file.read())
        
        # ฟังก์ชัน check_chapter_2 เราเขียนไว้ให้คืนค่าแค่ issues (ไม่มี summary)
        issues = check_chapter_2(temp_in)
        
        annotate_and_save_pdf(temp_in, local_out, issues)
        
        # ส่งแค่ issues (summary เป็น None)
        csv_data = generate_csv(issues, summary=None) 
        
        return StreamingResponse(
            io.StringIO(csv_data), 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('report_chapter1.csv')}"}
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