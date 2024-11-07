"""Service registry and dependency injection"""
from typing import Dict, Type, Any
from app.services.voice_cloning import VoiceCloningService
from app.services.translation import TranslationService
from app.services.storage_service import StorageService
from app.core.cache import cache_manager
import logging

logger = logging.getLogger(__name__)

class ServiceRegistry:
    _instances: Dict[Type, Any] = {}
    
    @classmethod
    def get_service(cls, service_class: Type) -> Any:
        """Get or create service instance"""
        if service_class not in cls._instances:
            logger.debug(f"Creating new instance of {service_class.__name__}")
            cls._instances[service_class] = service_class()
        return cls._instances[service_class]
    
    @classmethod
    def clear(cls):
        """Clear all service instances"""
        cls._instances.clear()

# Service factory functions
def get_voice_service() -> VoiceCloningService:
    return ServiceRegistry.get_service(VoiceCloningService)

def get_translation_service() -> TranslationService:
    return ServiceRegistry.get_service(TranslationService)

def get_storage_service() -> StorageService:
    return ServiceRegistry.get_service(StorageService) 