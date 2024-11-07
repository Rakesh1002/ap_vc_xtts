import hvac
from typing import Dict, Any, Optional
import os
from functools import lru_cache
import logging
from app.core.errors import AudioProcessingError, ErrorCodes, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)

class SecretsManager:
    def __init__(self):
        self.client = self._initialize_client()
        self.mount_point = "kv"
        self.secret_path = "audio-processing"
        
    def _initialize_client(self) -> hvac.Client:
        try:
            client = hvac.Client(
                url=os.getenv('VAULT_ADDR', 'http://vault:8200'),
                token=os.getenv('VAULT_TOKEN')
            )
            
            if not client.is_authenticated():
                raise AudioProcessingError(
                    message="Failed to authenticate with Vault",
                    error_code=ErrorCodes.SYSTEM_ERROR,
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.CRITICAL
                )
            
            return client
            
        except Exception as e:
            logger.error(f"Failed to initialize Vault client: {str(e)}")
            raise
    
    def get_secret(self, key: str) -> Optional[str]:
        try:
            secret = self.client.secrets.kv.v2.read_secret_version(
                path=f"{self.secret_path}/{key}",
                mount_point=self.mount_point
            )
            return secret['data']['data'].get(key)
        except Exception as e:
            logger.error(f"Failed to retrieve secret {key}: {str(e)}")
            return None
    
    def set_secret(self, key: str, value: str) -> bool:
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=f"{self.secret_path}/{key}",
                secret=dict([(key, value)]),
                mount_point=self.mount_point
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set secret {key}: {str(e)}")
            return False
    
    def rotate_secret(self, key: str, new_value: str) -> bool:
        try:
            # Get current version
            current = self.client.secrets.kv.v2.read_secret_version(
                path=f"{self.secret_path}/{key}",
                mount_point=self.mount_point
            )
            
            # Create new version
            success = self.set_secret(key, new_value)
            
            if success:
                # Keep track of rotation
                logger.info(f"Successfully rotated secret {key}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to rotate secret {key}: {str(e)}")
            return False

@lru_cache()
def get_secrets_manager() -> SecretsManager:
    return SecretsManager() 