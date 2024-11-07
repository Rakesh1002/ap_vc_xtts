from fastapi import HTTPException
from typing import Optional, Dict, Any, List
import traceback
from datetime import datetime
import logging
from enum import Enum
import json
import uuid

logger = logging.getLogger(__name__)

class ErrorSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    PROCESSING = "processing"
    STORAGE = "storage"
    MODEL = "model"
    SYSTEM = "system"

class AudioProcessingError(Exception):
    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.PROCESSING,
        error_id: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
        self.severity = severity
        self.category = category
        self.error_id = error_id or str(uuid.uuid4())
        self.timestamp = datetime.utcnow()
        self.traceback = self._get_traceback()
        
        # Log the error
        self._log_error()
        
        super().__init__(self.message)
    
    def _get_traceback(self) -> List[str]:
        if self.original_error:
            return traceback.format_exception(
                type(self.original_error),
                self.original_error,
                self.original_error.__traceback__
            )
        return traceback.format_stack()

    def _log_error(self):
        error_info = self.to_dict()
        log_message = json.dumps(error_info, default=str)
        
        if self.severity in (ErrorSeverity.HIGH, ErrorSeverity.CRITICAL):
            logger.error(f"Critical Error: {log_message}")
            # Here you could add notifications for critical errors
            # self._notify_critical_error(error_info)
        else:
            logger.warning(f"Error: {log_message}")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "severity": self.severity,
            "category": self.category,
            "timestamp": self.timestamp.isoformat(),
            "traceback": self.traceback if self.severity in (ErrorSeverity.HIGH, ErrorSeverity.CRITICAL) else None
        }

class ErrorCodes:
    # Validation Errors
    INVALID_AUDIO_FORMAT = "INVALID_AUDIO_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_LANGUAGE = "INVALID_LANGUAGE"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    
    # Storage Errors
    UPLOAD_FAILED = "UPLOAD_FAILED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    STORAGE_QUOTA_EXCEEDED = "STORAGE_QUOTA_EXCEEDED"
    
    # Processing Errors
    PROCESSING_FAILED = "PROCESSING_FAILED"
    TIMEOUT = "TIMEOUT"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    
    # Model Errors
    MODEL_ERROR = "MODEL_ERROR"
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    INFERENCE_ERROR = "INFERENCE_ERROR"
    
    # System Errors
    SYSTEM_ERROR = "SYSTEM_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    WORKER_ERROR = "WORKER_ERROR"

def handle_error(e: Exception, context: Dict[str, Any] = None) -> AudioProcessingError:
    """Convert various exceptions to AudioProcessingError with appropriate categorization"""
    if isinstance(e, AudioProcessingError):
        return e
        
    error_context = {
        "original_error": str(e),
        **(context or {})
    }
    
    if isinstance(e, MemoryError):
        return AudioProcessingError(
            message="System out of memory",
            error_code=ErrorCodes.RESOURCE_EXHAUSTED,
            details=error_context,
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.SYSTEM,
            original_error=e
        )
    
    if isinstance(e, TimeoutError):
        return AudioProcessingError(
            message="Operation timed out",
            error_code=ErrorCodes.TIMEOUT,
            details=error_context,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PROCESSING,
            original_error=e
        )
    
    # Default error handling
    return AudioProcessingError(
        message="An unexpected error occurred",
        error_code=ErrorCodes.SYSTEM_ERROR,
        details=error_context,
        severity=ErrorSeverity.HIGH,
        category=ErrorCategory.SYSTEM,
        original_error=e
    )