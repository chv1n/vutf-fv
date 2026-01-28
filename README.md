# Linux
# 1.สร้าง venv
python3 -m venv venv

# 2.Activate venv
source venv/bin/activate

# 3.ติดตั้ง dependency ใหม่
pip install fastapi uvicorn pymupdf python-multipart pymupdf-layout tqdm

# 4.run
python main.py

# เมื่อเลิกใช้งาน
# 4.ออกจาก venv
deactivate

# 5.ลบ venv เก่า
rm -rf venv


# Windows
# 1.สร้าง venv
python -m venv venv

# 2.Activate venv
.\venv\Scripts\activate

# 3.ติดตั้ง dependency ใหม่
pip install fastapi uvicorn pymupdf python-multipart pymupdf-layout tqdm

# 4.run
python main.py

# เมื่อเลิกใช้งาน
# 5.ออกจาก venv เ
deactivate

# 6.ลบ venv เก่า
rmdir /s /q venv

# การส่งไฟล์มาตรวจ (ผ่าน Postman)
1. สร้าง Request ใหม่ เลือก Method เป็น **POST**
2. ใส่ URL: `http://localhost:8002/check_pdf`
3. ไปที่แท็บ **Body** -> เลือก **form-data**
4. ตั้งค่า Key:
   - **Key:** ใส่ `file`
   - **Value:** เลือกไฟล์ PDF จากเครื่อง
5. กด **Send**
   - หากสำเร็จ จะได้ไฟล์ `.csv` ตอบกลับมา

*ไฟล์ output ที่แสดงการตรวจจะอยู่ในโฟลเดอร์ output_files
