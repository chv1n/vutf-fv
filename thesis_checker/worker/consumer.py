# thesis_checker/worker/consumer.py
"""
RabbitMQ consumer that processes PDF verification jobs
"""
import json
import os
import tempfile
import pika
import io
import csv
from models import Issue
from typing import List

from .config import config
from .s3_client import s3_client
from .producer import result_producer


def generate_csv(issues: List[Issue]) -> str:
    """Generates CSV data from a list of issues."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Page", "Code", "Severity", "Message", "BBox"])
    for i in issues:
        writer.writerow([i.page, i.code, i.severity, i.message, str(i.bbox)])
    return output.getvalue()


class JobConsumer:
    """Consumes verification jobs from RabbitMQ and processes them"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
    
    def connect(self):
        """Establish connection to RabbitMQ"""
        credentials = pika.PlainCredentials(
            config.RABBITMQ_USER,
            config.RABBITMQ_PASSWORD
        )
        parameters = pika.ConnectionParameters(
            host=config.RABBITMQ_HOST,
            port=config.RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=1800, 
            blocked_connection_timeout=900,
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        
        # Declare exchange and queue
        self.channel.exchange_declare(
            exchange=config.EXCHANGE_NAME,
            exchange_type='direct',
            durable=True
        )
        self.channel.queue_declare(queue=config.JOB_QUEUE, durable=True)
        self.channel.queue_bind(
            exchange=config.EXCHANGE_NAME,
            queue=config.JOB_QUEUE,
            routing_key=config.JOB_QUEUE
        )
        
        # Fair dispatch - one message at a time
        self.channel.basic_qos(prefetch_count=1)
    
    def process_job(self, job: dict) -> tuple:
        """
        Process a single verification job
        
        Args:
            job: Job message from queue
            
        Returns:
            Tuple of (success: bool, pdf_url: str, csv_url: str, result_name: str, file_size: int, error: str)
        """
        # Import here to avoid circular imports and ensure proper path
        import sys
        worker_dir = os.path.dirname(os.path.abspath(__file__))
        thesis_checker_dir = os.path.dirname(worker_dir)
        if thesis_checker_dir not in sys.path:
            sys.path.insert(0, thesis_checker_dir)
        
        from core.validator import run_all_checks
        from core.annotator import annotate_and_save_pdf
        
        job_id = job.get('job_id')
        submission_id = job.get('submission_id')
        attempt = job.get('attempt', job_id)
        file_url = job.get('file_url')
        file_name = job.get('file_name', 'document.pdf')
        job_config = job.get('config', {})
        
        print(f"[Consumer] Processing job {job_id} for submission {submission_id}")
        
        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 1. Download PDF from S3
                input_path = os.path.join(temp_dir, file_name)
                print(f"[Consumer] Downloading file...")
                s3_client.download_file(file_url, input_path)
                
                # 2. Temporarily override config with job config
                # Write job config to a temp config.json so run_all_checks picks it up
                if job_config:
                    config_path = os.path.join(thesis_checker_dir, 'config.json')
                    backup_config = None
                    
                    # Backup existing config
                    if os.path.exists(config_path):
                        with open(config_path, 'r', encoding='utf-8') as f:
                            backup_config = f.read()
                    
                    # Write job config
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(job_config, f, ensure_ascii=False, indent=2)
                    
                    try:
                        # Reload config module
                        import importlib
                        import config as cfg_module
                        importlib.reload(cfg_module)
                        
                        # 3. Run validation checks
                        print(f"[Consumer] Running validation checks...")
                        issues = run_all_checks(input_path)
                    finally:
                        # Restore original config
                        if backup_config:
                            with open(config_path, 'w', encoding='utf-8') as f:
                                f.write(backup_config)
                else:
                    # Use default config
                    print(f"[Consumer] Running validation checks with default config...")
                    issues = run_all_checks(input_path)
                
                # 4. Generate annotated PDF
                base_name = os.path.splitext(file_name)[0]
                output_filename = f"result_{base_name}.pdf"
                output_path = os.path.join(temp_dir, output_filename)
                annotate_and_save_pdf(input_path, output_path, issues)
                
                file_size = os.path.getsize(output_path)
                
                # 5. Upload result PDF to S3
                pdf_s3_key = s3_client.generate_result_key(output_filename, submission_id, attempt)
                print(f"[Consumer] Uploading result PDF to S3: {pdf_s3_key}")
                pdf_url = s3_client.upload_file(output_path, pdf_s3_key)

                # 6. Generate and Upload CSV report
                csv_url = None
                if issues:
                    csv_filename = f"report_{base_name}.csv"
                    csv_path = os.path.join(temp_dir, csv_filename)
                    
                    csv_data = generate_csv(issues)
                    with open(csv_path, "w", encoding="utf-8-sig") as f:
                        f.write(csv_data)
                    
                    csv_s3_key = s3_client.generate_result_key(csv_filename, submission_id, attempt)
                    print(f"[Consumer] Uploading CSV report to S3: {csv_s3_key}")
                    csv_url = s3_client.upload_file(csv_path, csv_s3_key)

                print(f"[Consumer] Job {job_id} completed successfully with {len(issues)} issues found")
                return True, pdf_url, csv_url, output_filename, file_size, None
                
            except Exception as e:
                error_msg = str(e)
                print(f"[Consumer] Job {job_id} failed: {error_msg}")
                import traceback
                traceback.print_exc()
                return False, None, None, None, None, error_msg
    
    def on_message(self, channel, method, properties, body):
        """Callback for processing incoming messages"""
        try:
            job = json.loads(body)
            job_id = job.get('job_id', 'unknown')
            submission_id = job.get('submission_id')
            start_time = job.get('start_time')
            
            print(f"[Consumer] Received job: {job_id}")
            
            # Process the job
            success, pdf_url, csv_url, result_name, file_size, error = self.process_job(job)
            
            # Send result back to API
            result_producer.send_result(
                job_id=job_id,
                submission_id=submission_id,
                status='completed' if success else 'failed',
                result_file_url=pdf_url,
                result_csv_url=csv_url,
                result_file_name=result_name,
                result_file_size=file_size,
                error_message=error,
                start_time=start_time
            )
            
            # Acknowledge message
            channel.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f"[Consumer] Error processing message: {e}")
            import traceback
            traceback.print_exc()
            # Reject and requeue on error
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start(self):
        """Start consuming messages"""
        if not self.channel:
            self.connect()
        
        print(f"[Consumer] Waiting for jobs on queue: {config.JOB_QUEUE}")
        print("[Consumer] Press CTRL+C to exit")
        
        self.channel.basic_consume(
            queue=config.JOB_QUEUE,
            on_message_callback=self.on_message,
        )
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            print("\n[Consumer] Shutting down...")
            self.channel.stop_consuming()
        finally:
            if self.connection and self.connection.is_open:
                self.connection.close()


# Singleton instance
job_consumer = JobConsumer()
