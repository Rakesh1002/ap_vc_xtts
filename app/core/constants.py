from datetime import timedelta

MAX_AUDIO_SIZE = 1000 * 1024 * 1024  # 10MB
SUPPORTED_AUDIO_FORMATS = {'audio/wav', 'audio/mpeg', 'audio/ogg'} 

class CeleryQueues:
    VOICE = "voice-queue"
    TRANSLATION = "translation-queue"

class CeleryTasks:
    CLONE_VOICE = "app.workers.voice_tasks.clone_voice"
    TRANSLATE_AUDIO = "app.workers.translation_tasks.translate_audio"

class TaskTimeouts:
    VOICE_SOFT_TIMEOUT = 3300  # 55 minutes
    VOICE_HARD_TIMEOUT = 3600  # 60 minutes
    TRANSLATION_SOFT_TIMEOUT = 1700  # ~28 minutes
    TRANSLATION_HARD_TIMEOUT = 1800  # 30 minutes