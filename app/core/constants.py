from datetime import timedelta
from enum import Enum

MAX_AUDIO_SIZE = 100 * 1024 * 1024  # 100MB
MIN_AUDIO_DURATION = 0.1  # 100ms
MAX_AUDIO_DURATION = 600  # 10 minutes

# Extended audio format support
SUPPORTED_AUDIO_FORMATS = {
    # WAV formats
    'audio/wav',
    'audio/x-wav',
    'audio/wave',
    'audio/x-pn-wav',
    
    # MP3 formats
    'audio/mpeg',
    'audio/mp3',
    'audio/mpeg3',
    'audio/x-mpeg-3',
    
    # Ogg formats (including Opus)
    'audio/ogg',
    'audio/opus',
    'audio/x-opus',
    'audio/ogg; codecs=opus',
    'application/ogg',
    
    # AAC formats
    'audio/aac',
    'audio/x-aac',
    'audio/aacp',
    'audio/3gpp',
    'audio/3gpp2',
    
    # M4A formats
    'audio/x-m4a',
    'audio/mp4',
    'audio/mp4a-latm',
    
    # FLAC formats
    'audio/flac',
    'audio/x-flac',
    
    # WebM formats
    'audio/webm',
    'audio/webm; codecs=opus',
    
    # Other formats
    'audio/x-ms-wma',  # Windows Media Audio
    'audio/vorbis',    # Vorbis
    'audio/speex',     # Speex
}

SUPPORTED_AUDIO_EXTENSIONS = {
    # Common formats
    '.wav', '.mp3', '.ogg', '.m4a', '.aac',
    # Additional formats
    '.opus', '.flac', '.wma', '.webm', '.3gp',
    '.spx', '.wv', '.oga', '.mp4', '.m4b',
    '.m4p', '.m4r'
}

# Audio conversion settings
PROCESSING_SAMPLE_RATE = 48000  # Target sample rate for processing
PROCESSING_CHANNELS = 1         # Convert to mono for processing
PROCESSING_FORMAT = 'wav'       # Internal processing format

class CeleryQueues:
    VOICE = "voice-queue"
    TRANSLATION = "translation-queue"
    SPEAKER = "speaker-queue"
    DENOISER = "denoiser-queue"
    SPECTRAL = "spectral-queue"

class CeleryTasks:
    CLONE_VOICE = "app.workers.voice_tasks.clone_voice"
    TRANSLATE_AUDIO = "app.workers.translation_tasks.translate_audio"
    DIARIZE_SPEAKERS = "app.workers.speaker_tasks.diarize_speakers"
    EXTRACT_SPEAKERS = "app.workers.speaker_tasks.extract_speakers"
    DENOISE_AUDIO = "app.workers.denoiser_tasks.denoise_audio"
    SPECTRAL_DENOISE_AUDIO = "app.workers.spectral_denoiser_tasks.denoise_audio"

class TaskTimeouts:
    VOICE_SOFT_TIMEOUT = 3300  # 55 minutes
    VOICE_HARD_TIMEOUT = 3600  # 60 minutes
    TRANSLATION_SOFT_TIMEOUT = 1700  # ~28 minutes
    TRANSLATION_HARD_TIMEOUT = 1800  # 30 minutes
    DENOISER_SOFT_TIMEOUT = 900  # 15 minutes
    DENOISER_HARD_TIMEOUT = 1000  # ~16.5 minutes