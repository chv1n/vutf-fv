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
    
    def _is_connected(self) -> bool:
        """Check if connection and channel are open"""
        return (
            self.connection is not None 
            and self.connection.is_open 
            and self.channel is not None 
            and self.channel.is_open
        )
    
    def connect(self):
        """Establish connection to RabbitMQ"""
        # Close existing connection if any
        self.close()
        
        credentials = pika.PlainCredentials(
            config.RABBITMQ_USER,
            config.RABBITMQ_PASSWORD
        )
        parameters = pika.ConnectionParameters(
            host=config.RABBITMQ_HOST,
            port=config.RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=1800,  # Keep connection alive
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
        self.channel.queue_declare(queue=config.RESULT_QUEUE, durable=True)
        self.channel.queue_bind(
            exchange=config.EXCHANGE_NAME,
            queue=config.RESULT_QUEUE,
            routing_key=config.RESULT_QUEUE
        )
        print("[Producer] Connected to RabbitMQ")
    
    def _ensure_connected(self):
        """Ensure connection is established, reconnect if needed"""
        if not self._is_connected():
            print("[Producer] Connection lost, reconnecting...")
            self.connect()
    
    def send_result(
        self,
        job_id: str,
        submission_id: int,
        status: str,
        result_file_url: str = None,
        result_csv_url: str = None,
        result_file_name: str = None,
        result_file_size: int = None,
        error_message: str = None,
        start_time: str = None
    ):
        """
        Send verification result to the result queue
        
        Args:
            job_id: Original job ID
            submission_id: Submission ID from database
            status: 'completed' or 'failed'
            result_file_url: S3 URL of result PDF (if completed)
            result_csv_url: S3 URL of result CSV (if completed)
            result_file_name: Result file name (if completed)
            error_message: Error description (if failed)
        """
        # Reconnect if channel is closed
        self._ensure_connected()
        
        message = {
            'job_id': job_id,
            'submission_id': submission_id,
            'status': status,
            'result_file_url': result_file_url,
            'result_csv_url': result_csv_url,
            'result_file_name': result_file_name,
            'result_file_size': result_file_size,
            'error_message': error_message,
            'completed_at': datetime.utcnow().isoformat() + 'Z',
            'start_time': start_time,
        }
        
        try:
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
        except pika.exceptions.AMQPError as e:
            print(f"[Producer] Publish failed, retrying: {e}")
            self.connect()
            self.channel.basic_publish(
                exchange=config.EXCHANGE_NAME,
                routing_key=config.RESULT_QUEUE,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json',
                )
            )
            print(f"[Producer] Result sent for job {job_id}: {status} (after retry)")
    
    def close(self):
        """Close connection"""
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
        except Exception:
            pass
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception:
            pass
        self.channel = None
        self.connection = None


# Singleton instance
result_producer = ResultProducer()
