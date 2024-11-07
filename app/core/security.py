"""Security utilities for authentication and authorization"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import get_settings
import secrets
import logging
from fastapi import HTTPException, status
from app.core.metrics import ERROR_COUNT
import re
from app.core.errors import SecurityError, ErrorCodes

settings = get_settings()
logger = logging.getLogger(__name__)

# Password hashing configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Increased from default 10
)

# Constants
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
MIN_PASSWORD_LENGTH = 8
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification failed: {str(e)}")
        ERROR_COUNT.labels(
            type="password_verification",
            severity="high",
            component="security"
        ).inc()
        return False

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

def validate_password(password: str) -> bool:
    """
    Validate password strength
    - At least 8 characters
    - Contains uppercase and lowercase letters
    - Contains numbers
    - Contains special characters
    """
    if not PASSWORD_PATTERN.match(password):
        raise SecurityError(
            message="Password does not meet security requirements",
            error_code=ErrorCodes.WEAK_PASSWORD,
            details={
                "requirements": [
                    "At least 8 characters",
                    "Contains uppercase and lowercase letters",
                    "Contains numbers",
                    "Contains special characters (@$!%*?&)"
                ]
            }
        )
    return True

def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    scopes: Optional[list] = None
) -> str:
    """Create JWT access token with optional expiration and scopes"""
    try:
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=ACCESS_TOKEN_EXPIRE_MINUTES
            )

        # Create token payload
        to_encode = {
            "exp": expire,
            "sub": str(subject),
            "iat": datetime.utcnow(),
            "jti": secrets.token_hex(16)  # Add unique token ID
        }
        
        # Add scopes if provided
        if scopes:
            to_encode["scopes"] = scopes

        # Create token with payload
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=ALGORITHM
        )
        
        return encoded_jwt

    except Exception as e:
        logger.error(f"Token creation failed: {str(e)}")
        ERROR_COUNT.labels(
            type="token_creation",
            severity="high",
            component="security"
        ).inc()
        raise SecurityError(
            message="Failed to create access token",
            error_code=ErrorCodes.TOKEN_CREATION_FAILED,
            original_error=e
        )

def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        
        # Verify token hasn't expired
        exp = payload.get("exp")
        if not exp or datetime.fromtimestamp(exp) < datetime.utcnow():
            raise SecurityError(
                message="Token has expired",
                error_code=ErrorCodes.TOKEN_EXPIRED
            )
            
        return payload

    except JWTError as e:
        logger.error(f"Token verification failed: {str(e)}")
        ERROR_COUNT.labels(
            type="token_verification",
            severity="medium",
            component="security"
        ).inc()
        raise SecurityError(
            message="Invalid token",
            error_code=ErrorCodes.INVALID_TOKEN,
            original_error=e
        )

def generate_reset_token(email: str) -> str:
    """Generate password reset token"""
    try:
        expires = datetime.utcnow() + timedelta(hours=24)
        return create_access_token(
            subject=email,
            expires_delta=expires - datetime.utcnow(),
            scopes=["password_reset"]
        )
    except Exception as e:
        logger.error(f"Reset token generation failed: {str(e)}")
        raise SecurityError(
            message="Failed to generate reset token",
            error_code=ErrorCodes.TOKEN_CREATION_FAILED,
            original_error=e
        )

def verify_reset_token(token: str) -> str:
    """Verify password reset token and return email"""
    try:
        payload = verify_token(token)
        
        # Verify token scope
        scopes = payload.get("scopes", [])
        if "password_reset" not in scopes:
            raise SecurityError(
                message="Invalid reset token",
                error_code=ErrorCodes.INVALID_TOKEN
            )
            
        return payload["sub"]

    except Exception as e:
        logger.error(f"Reset token verification failed: {str(e)}")
        raise SecurityError(
            message="Invalid or expired reset token",
            error_code=ErrorCodes.INVALID_TOKEN,
            original_error=e
        )

# Export all functions at module level
__all__ = [
    'verify_password',
    'get_password_hash',
    'validate_password',
    'create_access_token',
    'verify_token',
    'generate_reset_token',
    'verify_reset_token',
]