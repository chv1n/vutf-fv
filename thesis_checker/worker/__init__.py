# thesis_checker/worker/__init__.py
"""Worker package for RabbitMQ integration"""

from .config import config
from .s3_client import s3_client

__all__ = ['config', 's3_client', 'result_producer']
