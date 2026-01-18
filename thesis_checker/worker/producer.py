# thesis_checker/worker/producer.py
"""
RabbitMQ producer for sending results back to API
"""
import json
import pika
from datetime import datetime
from .config import config


class ResultProducer:
    """Publishes verification results to the result queue"""
    
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
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        
        # Declare exchange and queue
        self.channel.exchange_declare(
            exchange=config.EXCHANGE_NAME,
            exchange_type='direct',
            durable=True
        )
        self.channel.queue_declare(queue=config.RESULT_QUEUE, durable=True)
        self.channel.queue_bind(
            exchange=config.EXCHANGE_NAME,
            queue=config.RESULT_QUEUE,
            routing_key=config.RESULT_QUEUE
        )
    
    def send_result(
        self,
        job_id: str,
        submission_id: int,
        status: str,
        result_file_url: str = None,
        result_file_name: str = None,
        error_message: str = None
    ):
        """
        Send verification result to the result queue
        
        Args:
            job_id: Original job ID
            submission_id: Submission ID from database
            status: 'completed' or 'failed'
            result_file_url: S3 URL of result PDF (if completed)
            result_file_name: Result file name (if completed)
            error_message: Error description (if failed)
        """
        if not self.channel:
            self.connect()
        
        message = {
            'job_id': job_id,
            'submission_id': submission_id,
            'status': status,
            'result_file_url': result_file_url,
            'result_file_name': result_file_name,
            'error_message': error_message,
            'completed_at': datetime.utcnow().isoformat() + 'Z',
        }
        
        self.channel.basic_publish(
            exchange=config.EXCHANGE_NAME,
            routing_key=config.RESULT_QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type='application/json',
            )
        )
        
        print(f"[Producer] Result sent for job {job_id}: {status}")
    
    def close(self):
        """Close connection"""
        if self.connection and self.connection.is_open:
            self.connection.close()


# Singleton instance
result_producer = ResultProducer()
