# PDF Verification Worker

RabbitMQ worker สำหรับตรวจสอบไฟล์ PDF thesis

## Prerequisites

- Python 3.10+
- RabbitMQ server running
- AWS S3 access

## Installation

```bash
cd vutf-fp/thesis_checker
pip install pika boto3 python-dotenv requests PyMuPDF
```

## Configuration

สร้างไฟล์ `.env` ใน `thesis_checker/`:

```env
# AWS S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-southeast-7
S3_BUCKET=your_bucket_name
S3_ENDPOINT=https://s3.ap-southeast-7.amazonaws.com

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
JOB_QUEUE=pdf_verification_jobs
RESULT_QUEUE=pdf_verification_results
```

## Run Worker

```bash
cd vutf-fp/thesis_checker
python run_worker.py
```

## Architecture

```
run_worker.py        # Entry point
worker/
├── config.py        # Load environment variables
├── s3_client.py     # Download/Upload files from S3
├── consumer.py      # Receive jobs from RabbitMQ queue
└── producer.py      # Send results back to RabbitMQ queue
```

## Message Flow

1. API Service sends job to `pdf_verification_jobs` queue
2. Worker downloads PDF from S3 presigned URL
3. Worker runs validation checks (core/validator.py)
4. Worker generates annotated PDF (core/annotator.py)
5. Worker uploads result to S3
6. Worker sends result to `pdf_verification_results` queue
7. API Service receives result and saves to database

## Testing

1. Start RabbitMQ:
   ```bash
   docker compose up -d
   ```

2. Start API Service:
   ```bash
   cd vutf-api
   npm run start:dev
   ```

3. Start Worker:
   ```bash
   cd vutf-fp/thesis_checker
   python run_worker.py
   ```

4. Test via Postman:


   batch:
   ```
   POST http://localhost:3000/report-file/verify-batch
   Body: { "submissionIds": [1, 2, 3] }
   ```
