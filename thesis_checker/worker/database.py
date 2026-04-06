# thesis_checker/worker/database.py
"""
PostgreSQL database client for saving verification results directly
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from .config import config

logger = logging.getLogger(__name__)


class DatabaseClient:
    """PostgreSQL client for direct database operations"""

    def __init__(self):
        self.connection = None
        self.cursor = None

    def connect(self) -> None:
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(
                host=config.DATABASE_HOST,
                port=config.DATABASE_PORT,
                database=config.DATABASE_NAME,
                user=config.DATABASE_USER,
                password=config.DATABASE_PASSWORD,
                cursor_factory=RealDictCursor
            )
            self.connection.autocommit = True
            self.cursor = self.connection.cursor()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self) -> None:
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

    def save_verification_result(
        self,
        submission_id: int,
        status: str,
        file_url: str,
        csv_url: Optional[str],
        file_name: str,
        file_size: int,
        error_message: Optional[str],
        start_time: Optional[str]
    ) -> bool:
        """
        Save verification result directly to database

        Args:
            submission_id: Submission ID
            status: 'completed' or 'failed'
            file_url: S3 URL to result PDF
            csv_url: S3 URL to CSV report (optional)
            file_name: Result filename
            file_size: File size in bytes
            error_message: Error message if failed
            start_time: Job start time

        Returns:
            bool: Success status
        """
        try:
            # Determine verification status based on CSV presence
            verification_status = 'FAIL' if csv_url else 'PASS'
            if status == 'failed':
                verification_status = 'ERROR'

            # Convert status to submission status
            submission_status = 'COMPLETED' if status == 'completed' else 'FAILED'

            # Parse start_time
            started_at = None
            if start_time:
                try:
                    started_at = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                except:
                    started_at = datetime.utcnow()

            # Get next attempt number
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM report_file WHERE submission_id = %s",
                (submission_id,)
            )
            result = self.cursor.fetchone()
            attempt_number = (result['count'] if result else 0) + 1

            # Insert into report_file table
            insert_query = """
                INSERT INTO report_file (
                    submission_id,
                    attempt_number,
                    file_url,
                    csv_url,
                    file_name,
                    file_type,
                    file_size,
                    verification_status,
                    review_status,
                    started_at,
                    comment
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            self.cursor.execute(insert_query, (
                submission_id,
                attempt_number,
                file_url,
                csv_url,
                file_name,
                'pdf',
                file_size,
                verification_status,
                'PENDING',  # InstructorReviewStatus.PENDING
                started_at,
                error_message
            ))

            # Update submission status
            update_query = """
                UPDATE submissions
                SET status = %s
                WHERE submission_id = %s
            """
            self.cursor.execute(update_query, (submission_status, submission_id))

            logger.info(f"Saved verification result for submission {submission_id}, attempt {attempt_number}")
            return True

        except Exception as e:
            logger.error(f"Failed to save verification result: {e}")
            self.connection.rollback()
            return False

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()