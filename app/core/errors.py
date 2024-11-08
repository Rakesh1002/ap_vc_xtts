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
    PROCESSING = "processing"
    STORAGE = "storage"
    SECURITY = "security"
    SYSTEM = "system"
    MODEL = "model"

class ErrorCodes(str, Enum):
    # General errors
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    DATABASE_ERROR = "DATABASE_ERROR"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    
    # Processing errors
    PROCESSING_FAILED = "PROCESSING_FAILED"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    TIMEOUT = "TIMEOUT"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    TASK_CREATION_FAILED = "TASK_CREATION_FAILED"
    
    # Storage errors
    UPLOAD_FAILED = "UPLOAD_FAILED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    STORAGE_ERROR = "STORAGE_ERROR"
    
    # Audio Format Errors
    INVALID_AUDIO_FORMAT = "INVALID_AUDIO_FORMAT"
    UNSUPPORTED_AUDIO_FORMAT = "UNSUPPORTED_AUDIO_FORMAT"
    AUDIO_CONVERSION_FAILED = "AUDIO_CONVERSION_FAILED"
    AUDIO_VALIDATION_FAILED = "AUDIO_VALIDATION_FAILED"
    
    # Audio Processing Errors
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    AUDIO_TOO_SHORT = "AUDIO_TOO_SHORT"
    AUDIO_CORRUPTED = "AUDIO_CORRUPTED"
    AUDIO_EMPTY = "AUDIO_EMPTY"
    INVALID_SAMPLE_RATE = "INVALID_SAMPLE_RATE"
    INVALID_CHANNELS = "INVALID_CHANNELS"
    
    # Denoiser Specific Errors
    DENOISER_ERROR = "DENOISER_ERROR"
    DENOISER_NOT_INITIALIZED = "DENOISER_NOT_INITIALIZED"
    DENOISER_PROCESSING_FAILED = "DENOISER_PROCESSING_FAILED"
    DENOISER_INIT_ERROR = "DENOISER_INIT_ERROR"
    
    # Model errors
    MODEL_ERROR = "MODEL_ERROR"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_LOAD_ERROR = "MODEL_LOAD_ERROR"
    INFERENCE_ERROR = "INFERENCE_ERROR"
    
    # Hardware errors
    CUDA_ERROR = "CUDA_ERROR"
    MEMORY_ERROR = "MEMORY_ERROR"
    
    # File Operation Errors
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_READ_ERROR = "FILE_READ_ERROR"
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"
    FILE_DELETE_ERROR = "FILE_DELETE_ERROR"

class BaseError(Exception):
    """Base error class for all custom exceptions"""
    def __init__(
        self,
        message: str,
        error_code: ErrorCodes,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.error_id = str(uuid.uuid4())
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.severity = severity
        self.category = category
        self.timestamp = datetime.utcnow().isoformat()
        self.original_error = original_error
        self.traceback = None  # Will be set by error handler

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format"""
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "severity": self.severity,
            "category": self.category,
            "timestamp": self.timestamp,
            "traceback": self.traceback
        }

class SecurityError(BaseError):
    """Security-related errors"""
    def __init__(
        self,
        message: str,
        error_code: ErrorCodes,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            severity=severity,
            category=ErrorCategory.SECURITY,
            original_error=original_error
        )

class AudioProcessingError(BaseError):
    """Base exception for audio processing errors"""
    def __init__(
        self,
        message: str,
        error_code: ErrorCodes,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        category: ErrorCategory = ErrorCategory.PROCESSING,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details or {},
            severity=severity,
            category=category,
            original_error=original_error
        )

    def __str__(self):
        return f"{self.error_code}: {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }

class StorageError(BaseError):
    """Storage-related errors"""
    def __init__(
        self,
        message: str,
        error_code: ErrorCodes,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            severity=severity,
            category=ErrorCategory.STORAGE,
            original_error=original_error
        )

class ValidationError(BaseError):
    """Validation-related errors"""
    def __init__(
        self,
        message: str,
        error_code: ErrorCodes,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.LOW,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            severity=severity,
            category=ErrorCategory.VALIDATION,
            original_error=original_error
        )

class ModelError(BaseError):
    """Model-related errors"""
    def __init__(
        self,
        message: str,
        error_code: ErrorCodes,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            severity=severity,
            category=ErrorCategory.MODEL,
            original_error=original_error
        )

class DenoiserError(AudioProcessingError):
    """Errors specific to audio denoising"""
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCodes = ErrorCodes.DENOISER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details or {},
            severity=severity,
            category=ErrorCategory.PROCESSING,
            original_error=original_error
        )

class DatabaseError(BaseError):
    """Database-related errors"""
    def __init__(
        self,
        message: str,
        error_code: ErrorCodes = ErrorCodes.DATABASE_ERROR,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details or {},
            severity=severity,
            category=ErrorCategory.SYSTEM,
            original_error=original_error
        )

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