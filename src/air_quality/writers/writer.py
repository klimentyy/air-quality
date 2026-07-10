from abc import ABC, abstractmethod
import logging
import os
from polars import DataFrame

logger = logging.getLogger(__name__)

class DataWriter(ABC):
    @abstractmethod
    def write(self, df: DataFrame, target:str) -> None:
        """Save DataFrame"""
        pass

class LocalFileWriter(DataWriter):
    def write(self, df: DataFrame, target: str) -> None:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        df.write_parquet(target)
        logger.info(f"DataFrame successfully written to {target}")

class S3Writer(DataWriter):
    def write(self, df: DataFrame, target: str) -> None:
        import boto3
        import io

        buffer = io.BytesIO()
        df.write_parquet(buffer)
        buffer.seek(0)

        s3_client = boto3.client("s3")
        bucket_name = os.environ.get("DATA_HEALTH_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("DATA_HEALTH_BUCKET_NAME environment variable is not set")
        s3_client.upload_fileobj(buffer, bucket_name, target)
        logger.info(f"DataFrame successfully streamed directly to S3://{bucket_name}/{target}")