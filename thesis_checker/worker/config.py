# thesis_checker/worker/config.py
"""
Worker configuration loaded from environment variables
"""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class WorkerConfig:
    """Configuration for RabbitMQ and S3"""
    
    # RabbitMQ
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
    RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')
    JOB_QUEUE = os.getenv('JOB_QUEUE', 'pdf_verification_jobs')
    RESULT_QUEUE = os.getenv('RESULT_QUEUE', 'pdf_verification_results')
    EXCHANGE_NAME = 'pdf_verification'
    
    # S3 / AWS
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    AWS_REGION = os.getenv('AWS_REGION', 'ap-southeast-7')
    S3_BUCKET = os.getenv('S3_BUCKET', '')
    S3_ENDPOINT = os.getenv('S3_ENDPOINT', 'https://s3.ap-southeast-7.amazonaws.com')
    
    @classmethod
    def get_rabbitmq_url(cls) -> str:
        """Build RabbitMQ connection URL"""
        return f"amqp://{cls.RABBITMQ_USER}:{cls.RABBITMQ_PASSWORD}@{cls.RABBITMQ_HOST}:{cls.RABBITMQ_PORT}/"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required config values"""
        required = [
            cls.RABBITMQ_HOST,
            cls.AWS_ACCESS_KEY_ID,
            cls.AWS_SECRET_ACCESS_KEY,
            cls.S3_BUCKET,
        ]
        return all(required)


# Singleton instance
config = WorkerConfig()
