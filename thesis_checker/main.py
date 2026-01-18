import os, io, csv, json
from fastapi import FastAPI, UploadFile, File, Body
from fastapi.responses import StreamingResponse, JSONResponse
from config import OUTPUT_DIR, DEFAULT_CONFIG, load_config
from urllib.parse import quote
import uvicorn

from config import OUTPUT_DIR
from core.validator import run_all_checks
from core.annotator import annotate_and_save_pdf

app = FastAPI()

def generate_csv(issues):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Page", "Code", "Severity", "Message", "BBox"])
    for i in issues: writer.writerow([i.page, i.code, i.severity, i.message, str(i.bbox)])
    return output.getvalue()

@app.post("/check_pdf")
async def check_pdf(file: UploadFile = File(...)):
    temp_in = f"temp_{file.filename}"
    local_out = os.path.join(OUTPUT_DIR, f"debug_{file.filename}")
    try:
        with open(temp_in, "wb") as f: f.write(await file.read())
        issues = run_all_checks(temp_in)
        annotate_and_save_pdf(temp_in, local_out, issues)
        csv_data = generate_csv(issues)
        return StreamingResponse(io.StringIO(csv_data), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('report.csv')}"})
    except Exception as e: return JSONResponse(status_code=500, content={"error": str(e)})
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