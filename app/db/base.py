from app.db.base_class import Base  # noqa

# Import all models here for Alembic to detect them
from app.models.user import User  # noqa
from app.models.audio import (  # noqa
    Voice,
    CloningJob,
    TranslationJob,
    SpeakerJob
)

# This ensures all models are registered with Base.metadata
__all__ = [
    "Base",
    "User",
    "Voice",
    "CloningJob",
    "TranslationJob",
    "SpeakerJob"
] 