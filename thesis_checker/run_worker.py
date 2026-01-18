#!/usr/bin/env python3
# thesis_checker/run_worker.py
"""
Entry point for running the PDF verification worker.
This worker listens to RabbitMQ for verification jobs and processes them.

Usage:
    python run_worker.py

Make sure to set up .env file with:
    - RabbitMQ connection details
    - AWS S3 credentials
"""
import os
import sys

# Add thesis_checker to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worker.config import config
from worker.consumer import job_consumer


def main():
    """Main entry point"""
    print("=" * 50)
    print("PDF Verification Worker")
    print("=" * 50)
    
    # Validate configuration
    if not config.validate():
        print("[ERROR] Missing required configuration!")
        print("Please check your .env file has:")
        print("  - RABBITMQ_HOST")
        print("  - AWS_ACCESS_KEY_ID")
        print("  - AWS_SECRET_ACCESS_KEY")
        print("  - S3_BUCKET")
        sys.exit(1)
    
    print(f"[Config] RabbitMQ: {config.RABBITMQ_HOST}:{config.RABBITMQ_PORT}")
    print(f"[Config] Job Queue: {config.JOB_QUEUE}")
    print(f"[Config] Result Queue: {config.RESULT_QUEUE}")
    print(f"[Config] S3 Bucket: {config.S3_BUCKET}")
    print("=" * 50)
    
    # Start consuming
    job_consumer.start()


if __name__ == "__main__":
    main()
