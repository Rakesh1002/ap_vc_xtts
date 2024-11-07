import logging
from typing import Any, Dict

def log_operation_start(logger: logging.Logger, operation: str, **kwargs):
    """Standard format for logging operation start"""
    logger.debug(f"Starting {operation}", extra=kwargs)

def log_operation_success(logger: logging.Logger, operation: str, **kwargs):
    """Standard format for logging operation success"""
    logger.info(f"Successfully completed {operation}", extra=kwargs)

def log_operation_error(logger: logging.Logger, operation: str, error: Exception, **kwargs):
    """Standard format for logging operation errors"""
    logger.error(f"Error in {operation}: {str(error)}", extra=kwargs) 