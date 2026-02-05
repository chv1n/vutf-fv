import os, io, csv, json
from fastapi import FastAPI, UploadFile, File, Body, Path, HTTPException 
from fastapi.responses import StreamingResponse, JSONResponse
from config import OUTPUT_DIR, DEFAULT_CONFIG, load_config
from urllib.parse import quote

# Import Validators
from core.chapter1_validator import GREEN, RED, RST, check_chapter_1
from core.chapter2_validator import check_chapter_2
from core.chapter_validator import validate_chapter
from core.validator import run_all_checks
from core.annotator import annotate_and_save_pdf

import uvicorn

app = FastAPI()

ANNOTATE = True

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

# ฟังก์ชันช่วยบันทึก CSV ลงเครื่อง
def save_csv_to_disk(csv_content: str, original_filename: str, prefix: str = "report"):
    # ตัดนามสกุลเดิมออก (เช่น .pdf) แล้วเติม .csv
    base_name = os.path.splitext(original_filename)[0]
    csv_filename = f"{prefix}_{base_name}.csv"
    csv_path = os.path.join(OUTPUT_DIR, csv_filename)
    
    try:
        with open(csv_path, "w", encoding="utf-8-sig") as f: # utf-8-sig เพื่อให้ Excel เปิดอ่านภาษาไทยได้เลย
            f.write(csv_content)
        print(f"{GREEN}Saved CSV report locally to: {csv_path}{RST}")
    except Exception as e:
        print(f"{RED}Failed to save CSV locally: {e}{RST}")

# -------------------------------------------------------------------------------------------------------
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

# -------------------------------------------------------------------------------------------------------

@app.post("/check_chapter/{chapter_num}")
async def check_specific_chapter(
    chapter_num: int = Path(..., title="The chapter number to validate", ge=1, le=5),
    file: UploadFile = File(...) 
):
    temp_in = f"temp_chap{chapter_num}_{file.filename}"
    local_out = os.path.join(OUTPUT_DIR, f"debug_chap{chapter_num}_{file.filename}")
    
    try:
        with open(temp_in, "wb") as f: f.write(await file.read())
        
        issues = validate_chapter(temp_in, chapter_num=chapter_num)
        
        annotate_and_save_pdf(temp_in, local_out, issues)
        
        csv_data = generate_csv(issues)
        
        # [ADDED] บันทึกไฟล์ CSV ลงเครื่อง Server
        save_csv_to_disk(csv_data, file.filename, prefix=f"report_chap{chapter_num}")
        
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
        
        issues = check_chapter_1(temp_in)
        
        annotate_and_save_pdf(temp_in, local_out, issues)
        
        csv_data = generate_csv(issues, summary=None) 
        
        # [ADDED] บันทึกไฟล์ CSV ลงเครื่อง Server
        save_csv_to_disk(csv_data, file.filename, prefix="report_chap1")
        
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
        
        issues = check_chapter_2(temp_in)
        
        annotate_and_save_pdf(temp_in, local_out, issues)
        
        csv_data = generate_csv(issues, summary=None) 
        
        # [ADDED] บันทึกไฟล์ CSV ลงเครื่อง Server
        save_csv_to_disk(csv_data, file.filename, prefix="report_chap2")
        
        return StreamingResponse(
            io.StringIO(csv_data), 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('report_chapter2.csv')}"}
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