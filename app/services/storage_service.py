import boto3
import logging
from botocore.exceptions import ClientError
from typing import BinaryIO, Optional
from app.core.config import get_settings
from urllib.parse import urlparse
import requests
import yt_dlp
import mimetypes
from botocore.config import Config
import os
import time
from pathlib import Path
import asyncio
import random

logger = logging.getLogger(__name__)

class DownloadError(Exception):
    pass

class StorageService:
    def __init__(self):
        settings = get_settings()
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
        self.temp_dir = Path("/tmp/downloads")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # List of user agents to rotate
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ]

    async def _download_youtube(self, url: str) -> Optional[str]:
        """Download YouTube video audio with enhanced anti-bot measures"""
        try:
            # Generate a random user agent
            user_agent = random.choice(self.user_agents)
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(self.temp_dir / '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'extract_audio': True,
                'audio_format': 'mp3',
                'nocheckcertificate': True,
                'http_headers': {
                    'User-Agent': user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                },
                'socket_timeout': 30,
                'retries': 5,
                'fragment_retries': 10,
                'skip_download': False,
                'continuedl': True,
                'external_downloader': 'aria2c',  # Use aria2c for better download handling
                'external_downloader_args': ['--min-split-size=1M', '--max-connection-per-server=16'],
                'sleep_interval': 3,  # Add delay between requests
                'max_sleep_interval': 6,
                'sleep_interval_requests': 1
            }

            # Try to use cookies if available
            cookie_file = Path("youtube.cookies")
            if cookie_file.exists():
                ydl_opts['cookiefile'] = str(cookie_file)

            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Run extract_info in a thread pool
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                if info is None:
                    raise Exception("Failed to extract video information")
                
                # Get the downloaded file path
                file_path = str(self.temp_dir / f"{info['id']}.mp3")
                if not os.path.exists(file_path):
                    raise Exception(f"Downloaded file not found at {file_path}")
                
                return file_path
                
        except Exception as e:
            logger.error(f"YouTube download error: {str(e)}")
            # Try alternative download method if first attempt fails
            return await self._fallback_youtube_download(url)

    async def _fallback_youtube_download(self, url: str) -> Optional[str]:
        """Fallback method for YouTube downloads"""
        try:
            # Use different format and options for fallback
            ydl_opts = {
                'format': 'worstaudio/worst',  # Try lowest quality first
                'outtmpl': str(self.temp_dir / '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'extract_audio': True,
                'audio_format': 'mp3',
                'sleep_interval': 5,
                'max_sleep_interval': 10,
                'http_headers': {
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': '*/*',
                },
            }
            
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                if info is None:
                    raise Exception("Failed to extract video information in fallback")
                
                file_path = str(self.temp_dir / f"{info['id']}.mp3")
                if not os.path.exists(file_path):
                    raise Exception(f"Downloaded file not found at {file_path}")
                
                return file_path
                
        except Exception as e:
            logger.error(f"Fallback YouTube download error: {str(e)}")
            raise DownloadError(f"Failed to download from URL {url}: {str(e)}")

    async def upload_file(self, file: BinaryIO, key: str) -> str:
        """Upload a file to S3 with multipart support"""
        try:
            content_type, _ = mimetypes.guess_type(key)
            content_type = content_type or 'application/octet-stream'
            
            if file.seekable() and file.tell() > get_settings().MULTIPART_THRESHOLD:
                transfer_config = boto3.s3.transfer.TransferConfig(
                    multipart_threshold=get_settings().MULTIPART_THRESHOLD,
                    max_concurrency=10
                )
                self.s3_client.upload_fileobj(
                    file, 
                    self.bucket, 
                    key,
                    ExtraArgs={'ContentType': content_type},
                    Config=transfer_config
                )
            else:
                self.s3_client.upload_fileobj(
                    file, 
                    self.bucket, 
                    key,
                    ExtraArgs={'ContentType': content_type}
                )
            
            url = f"https://{self.bucket}.s3.amazonaws.com/{key}"
            logger.info(f"Successfully uploaded file to {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {str(e)}")
            raise

    async def download_from_url(self, url: str) -> str:
        """Download file from URL and return local path"""
        try:
            if "youtube.com" in url or "youtu.be" in url:
                return await self._download_youtube(url)

            # Create downloads directory if it doesn't exist
            os.makedirs(get_settings().DOWNLOAD_DIR, exist_ok=True)
            
            # Generate a unique filename
            filename = f"{time.time_ns()}_{url.split('/')[-1]}"
            local_path = os.path.join(get_settings().DOWNLOAD_DIR, filename)
            
            if 's3.amazonaws.com' in url:
                # Parse S3 URL
                parsed_url = urlparse(url)
                bucket = parsed_url.netloc.split('.')[0]
                key = parsed_url.path.lstrip('/')
                
                # Download from S3 to local file
                self.s3_client.download_file(bucket, key, local_path)
            else:
                # Download from HTTP URL
                response = requests.get(url, stream=True)
                response.raise_for_status()
                
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            logger.info(f"Downloaded file to local path: {local_path}")
            return local_path
                
        except Exception as e:
            logger.error(f"Failed to download from URL {url}: {str(e)}")
            raise 