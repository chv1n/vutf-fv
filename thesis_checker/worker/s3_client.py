# thesis_checker/worker/s3_client.py
"""
S3 client for downloading and uploading files
"""
import os
import boto3
import mimetypes
from botocore.config import Config
from .config import config


class S3Client:
    """AWS S3 client wrapper for file operations"""
    
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION,
            endpoint_url=config.S3_ENDPOINT,
            config=Config(signature_version='s3v4'),
        )
        self.bucket = config.S3_BUCKET
    
    def download_file(self, url: str, local_path: str) -> str:
     
        import requests
        
        # If it's a presigned URL, download via HTTP
        if url.startswith('http'):
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            # Direct S3 download using key
            key = url.replace(f's3://{self.bucket}/', '')
            self.s3.download_file(self.bucket, key, local_path)
        
        return local_path
    
    def upload_file(self, local_path: str, s3_key: str) -> str:
        """
        Upload local file to S3
        
        Args:
            local_path: Path to local file
            s3_key: S3 object key (path in bucket)
            
        Returns:
            S3 URL of uploaded file
        """
        
        content_type, _ = mimetypes.guess_type(local_path)
        if content_type is None:
            content_type = 'application/octet-stream'
            
        # Upload file
        self.s3.upload_file(
            local_path,
            self.bucket,
            s3_key,
            ExtraArgs={'ContentType': content_type}
        )
        
        # Generate presigned URL (valid for 7 days)
        url = self.s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': s3_key},
            ExpiresIn=604800  # 7 days
        )
        
        return url
    
    def generate_result_key(self, filename: str, submission_id: int, sub_folder=None) -> str:
        """
        Generate S3 key for result file
        Args:
            filename: The final filename (e.g., result_doc.pdf)
            submission_id: Submission ID
            sub_folder ในที่นี้จะเป็นเลขครั้งที่ (เช่น 1, 2, 3) ที่ส่งมาจาก Consumer
        """
        # Logic การสร้าง Path
        if sub_folder:
            return f"reports/{submission_id}/{sub_folder}/{filename}"
        else:
            return f"reports/{submission_id}/{filename}"


# Singleton instance
s3_client = S3Client()
