from yt_dlp import YoutubeDL
import requests
from pathlib import Path
import tempfile
from typing import Optional, Tuple
from app.core.errors import AudioProcessingError, ErrorCodes, ErrorCategory, ErrorSeverity
import logging
from urllib.parse import urlparse
import magic

logger = logging.getLogger(__name__)

class MediaExtractor:
    SUPPORTED_DOMAINS = {
        'youtube.com', 'youtu.be',
        'tiktok.com',
        'instagram.com',
        'soundcloud.com'
    }

    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'outtmpl': '%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True
        }

    async def extract_audio(self, source: str) -> Tuple[str, str]:
        """Extract audio from various sources (URL or direct file)"""
        try:
            if self._is_url(source):
                return await self._handle_url(source)
            return await self._handle_direct_file(source)
        except Exception as e:
            raise AudioProcessingError(
                message=f"Failed to extract audio: {str(e)}",
                error_code=ErrorCodes.PROCESSING_FAILED,
                category=ErrorCategory.PROCESSING,
                severity=ErrorSeverity.HIGH,
                original_error=e
            )

    def _is_url(self, source: str) -> bool:
        try:
            result = urlparse(source)
            return all([result.scheme, result.netloc])
        except:
            return False

    def _is_social_media_url(self, url: str) -> bool:
        domain = urlparse(url).netloc.replace('www.', '')
        return any(d in domain for d in self.SUPPORTED_DOMAINS)

    async def _handle_url(self, url: str) -> Tuple[str, str]:
        if self._is_social_media_url(url):
            return await self._extract_social_media(url)
        return await self._download_direct_audio(url)

    async def _extract_social_media(self, url: str) -> Tuple[str, str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info).replace('.webm', '.wav')
                    return filename, 'audio/wav'
            except Exception as e:
                raise AudioProcessingError(
                    message=f"Failed to extract from social media: {str(e)}",
                    error_code=ErrorCodes.PROCESSING_FAILED,
                    category=ErrorCategory.PROCESSING,
                    severity=ErrorSeverity.MEDIUM,
                    original_error=e
                )

    async def _download_direct_audio(self, url: str) -> Tuple[str, str]:
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Create temporary file
            suffix = Path(urlparse(url).path).suffix or '.tmp'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            
            # Download file
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file.close()
            
            # Detect mime type
            mime_type = magic.from_file(temp_file.name, mime=True)
            
            if not mime_type.startswith('audio/'):
                raise AudioProcessingError(
                    message="URL does not point to an audio file",
                    error_code=ErrorCodes.INVALID_AUDIO_FORMAT,
                    category=ErrorCategory.VALIDATION
                )
            
            return temp_file.name, mime_type
            
        except requests.exceptions.RequestException as e:
            raise AudioProcessingError(
                message=f"Failed to download audio: {str(e)}",
                error_code=ErrorCodes.DOWNLOAD_FAILED,
                category=ErrorCategory.STORAGE,
                severity=ErrorSeverity.MEDIUM,
                original_error=e
            )

    async def _handle_direct_file(self, file_path: str) -> Tuple[str, str]:
        mime_type = magic.from_file(file_path, mime=True)
        if not mime_type.startswith('audio/'):
            raise AudioProcessingError(
                message="File is not an audio file",
                error_code=ErrorCodes.INVALID_AUDIO_FORMAT,
                category=ErrorCategory.VALIDATION
            )
        return file_path, mime_type 