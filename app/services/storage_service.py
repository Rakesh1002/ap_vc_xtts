import boto3
import logging
from botocore.exceptions import ClientError
from typing import BinaryIO, Union
from app.core.config import get_settings
from urllib.parse import urlparse
import requests
import mimetypes
from botocore.config import Config
import os
import time
from pathlib import Path
from app.services.media_extractor import MediaExtractor
from app.core.errors import AudioProcessingError, ErrorCodes
import io

logger = logging.getLogger(__name__)
settings = get_settings()

class StorageService:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                retries=dict(
                    max_attempts=3,
                    mode='adaptive'
                ),
                max_pool_connections=50
            )
        )
        self.bucket = settings.S3_BUCKET
        self.temp_dir = Path(settings.DOWNLOAD_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file_path: str, key: str) -> str:
        """Upload file from local path to S3"""
        try:
            if not isinstance(file_path, (str, Path)):
                raise AudioProcessingError(
                    message=f"Invalid file_path type: {type(file_path)}. Expected str or Path.",
                    error_code=ErrorCodes.INVALID_INPUT
                )
            
            self.s3_client.upload_file(str(file_path), self.bucket, key)
            url = f"https://{self.bucket}.s3.amazonaws.com/{key}"
            logger.info(f"Successfully uploaded file to {url}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {str(e)}")
            raise AudioProcessingError(
                message="Failed to upload file",
                error_code=ErrorCodes.UPLOAD_FAILED,
                details={"error": str(e)},
                original_error=e
            )

    async def download_file(self, key: str, destination: str) -> None:
        """Download file from S3 to local destination"""
        try:
            if not isinstance(key, str):
                raise AudioProcessingError(
                    message=f"Invalid key type: {type(key)}. Expected str.",
                    error_code=ErrorCodes.INVALID_INPUT
                )
            
            self.s3_client.download_file(self.bucket, key, destination)
            logger.info(f"Successfully downloaded file {key} to {destination}")
            
        except Exception as e:
            logger.error(f"Failed to download file {key}: {e}")
            raise AudioProcessingError(
                message="Failed to download file",
                error_code=ErrorCodes.DOWNLOAD_FAILED,
                details={"error": str(e), "key": key},
                original_error=e
            )

    async def download_from_url(self, url: str) -> str:
        """Download file from URL (S3 or HTTP) to local temp directory"""
        try:
            # Parse URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            local_path = self.temp_dir / filename

            if parsed_url.netloc.endswith('s3.amazonaws.com'):
                # Download from S3
                key = parsed_url.path.lstrip('/')
                self.s3_client.download_file(
                    self.bucket,
                    key,
                    str(local_path)
                )
            else:
                # Download from HTTP URL
                response = requests.get(url, stream=True)
                response.raise_for_status()
                
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            logger.info(f"Successfully downloaded file to {local_path}")
            return str(local_path)

        except Exception as e:
            error_msg = f"Failed to download file from {url}: {str(e)}"
            logger.error(error_msg)
            raise AudioProcessingError(
                message="Failed to download file",
                error_code=ErrorCodes.DOWNLOAD_FAILED,
                details={"error": str(e), "url": url},
                original_error=e
            )

    async def delete_file(self, key: str):
        """Delete a file from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket,
                Key=key
            )
            logger.info(f"Successfully deleted file {key} from bucket {self.bucket}")
        except Exception as e:
            logger.error(f"Failed to delete file {key}: {e}")
            # Don't raise - just log the error

    def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for an S3 object"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': key
                },
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            raise AudioProcessingError(
                message="Failed to generate download URL",
                error_code=ErrorCodes.STORAGE_ERROR,
                details={"error": str(e), "key": key},
                original_error=e
            )

    async def get_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate a pre-signed URL for downloading a file"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': key
                },
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate pre-signed URL for {key}: {e}")
            raise AudioProcessingError(
                message="Failed to generate download URL",
                error_code=ErrorCodes.STORAGE_ERROR,
                details={"error": str(e), "key": key},
                original_error=e
            )

    def download_file_sync(self, key: str, local_path: str) -> None:
        """Synchronous version of download_file"""
        try:
            self.s3_client.download_file(self.bucket, key, local_path)
        except Exception as e:
            logger.error(f"Failed to download file from S3: {str(e)}")
            raise

    def upload_file_sync(self, file_data: Union[bytes, BinaryIO, str], key: str) -> str:
        """Synchronous version of upload_file"""
        try:
            if isinstance(file_data, (str, Path)):
                self.s3_client.upload_file(str(file_data), self.bucket, key)
            else:
                self.s3_client.upload_fileobj(file_data, self.bucket, key)
            return f"{self.bucket}/{key}"
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {str(e)}")
            raise