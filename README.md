# Audio Processing API

A high-performance audio processing service providing voice cloning and translation capabilities using state-of-the-art AI models (XTTS V2 and Faster Whisper).

## Table of Contents

- [Key Features](#key-features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [API Documentation](#api-documentation)
- [Architecture](#architecture)
- [Monitoring](#monitoring)
- [Contributing](#contributing)

## Key Features

### Voice Cloning (XTTS V2 0.22.0)

- High-quality speech synthesis with XTTS V2
- Multi-language voice cloning support
- Voice profile management with metadata
- Configurable voice parameters (speed, pitch)
- Support for WAV, MP3, OGG formats
- Batch processing capabilities
- Real-time status updates via WebSocket

### Audio Translation (Faster Whisper 1.0.3)

- Multi-language processing with auto-detection
- Support for social media audio extraction (YouTube, TikTok, Instagram)
- Large file handling up to 1GB with chunk processing
- Multiple output formats
- Batch translation support

### Speaker Analysis Features

The API provides two main speaker analysis capabilities:

#### 1. Speaker Diarization

Uses `pyannote/speaker-diarization-3.1` to identify who spoke when in an audio file.

## Prerequisites

### System Requirements

- Python 3.11+
- CUDA-capable GPU (recommended)
- 16GB+ RAM
- 100GB+ SSD storage
- PostgreSQL 14+
- Redis 5.0+
- FFmpeg

### Installation

1. System Dependencies:

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y \
    python3.11 python3.11-dev \
    ffmpeg libpq-dev postgresql-client \
    libsndfile1 sox libsox-dev \
    portaudio19-dev libasound2-dev \
    cmake pkg-config

# macOS
brew install python@3.11 ffmpeg postgresql@14 \
    sox portaudio cmake pkg-config
```

2. NVIDIA Setup (if using GPU):

```bash
# Install NVIDIA drivers
sudo ubuntu-drivers autoinstall

# Install CUDA toolkit
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run
sudo sh cuda_11.8.0_520.61.05_linux.run
```

## Quick Start

1. Clone and Setup:

```bash
# Clone repository
git clone https://github.com/yourusername/audio-processing-api
cd audio-processing-api

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install poetry
poetry install
```

2. Configure Environment:

```bash
cp .env.example .env
# Edit .env with your settings:
# - Database credentials
# - Redis connection
# - S3 storage details
# - JWT secret key
```

3. Start Services:

```bash
# Using Docker Compose (recommended for development)
docker-compose up -d

# Or start components individually:
docker-compose up -d db redis
poetry run uvicorn app.main:app --reload
poetry run celery -A app.core.celery_app worker -Q voice-queue,translation-queue
```

## Development Setup

### Database Setup

```bash
# Create database
createdb audio_processing

# Apply migrations
poetry run alembic upgrade head

# Create new migration
poetry run alembic revision --autogenerate -m "Description"
```

### Code Quality

```bash
# Format code
poetry run black app tests

# Sort imports
poetry run isort app tests

# Type checking
poetry run mypy app

# Run tests
poetry run pytest --cov=app
```

### Local Development

```bash
# Start API server with hot reload
poetry run uvicorn app.main:app --reload --port 8000

# Start Celery workers
poetry run celery -A app.core.celery_app worker \
    -Q voice-queue,translation-queue \
    --loglevel=info
```

## Production Deployment

### System Setup

1. Install Dependencies:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y nginx supervisor
```

2. Configure Nginx:

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

3. Configure Supervisor:

```ini
[program:api]
command=/path/to/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
directory=/path/to/audio-processing-api
user=ubuntu
autostart=true
autorestart=true

[program:celery_voice]
command=/path/to/venv/bin/celery -A app.core.celery_app worker -Q voice-queue --concurrency=2
directory=/path/to/audio-processing-api
user=ubuntu
autostart=true
autorestart=true

[program:celery_translation]
command=/path/to/venv/bin/celery -A app.core.celery_app worker -Q translation-queue --concurrency=4
directory=/path/to/audio-processing-api
user=ubuntu
autostart=true
autorestart=true
```

4. SSL Setup:

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d api.example.com
```

5. Start Services:

```bash
sudo systemctl start nginx
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

## API Documentation

### Authentication

#### Register User

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
           "email": "user@example.com",
           "password": "StrongPass123!",
           "full_name": "John Doe"
         }'
```

Response:

```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2024-01-01T12:00:00Z"
}
```

#### Get Access Token

```bash
curl -X POST "http://localhost:8000/api/v1/auth/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=user@example.com&password=StrongPass123!"
```

Response:

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Voice Cloning

#### List Voice Profiles

```bash
curl -X GET "http://localhost:8000/api/v1/voice/voices/" \
     -H "Authorization: Bearer ${TOKEN}"
```

Response:

```json
[
  {
    "id": 1,
    "name": "John's Voice",
    "description": "Male voice sample",
    "file_path": "voices/uuid/sample.wav",
    "created_at": "2024-01-01T12:00:00Z"
  }
]
```

#### Create Voice Profile

```bash
curl -X POST "http://localhost:8000/api/v1/voice/voices/" \
     -H "Authorization: Bearer ${TOKEN}" \
     -F "name=John's Voice" \
     -F "description=Male voice sample" \
     -F "file=@/path/to/voice_sample.wav"
```

Response:

```json
{
  "id": 1,
  "name": "John's Voice",
  "description": "Male voice sample",
  "file_path": "voices/uuid/sample.wav",
  "created_at": "2024-01-01T12:00:00Z"
}
```

#### Create Cloning Job

```bash
curl -X POST "http://localhost:8000/api/v1/voice/clone/" \
     -H "Authorization: Bearer ${TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
           "voice_id": 1,
           "input_text": "Hello, this is a test of voice cloning."
         }'
```

Response:

```json
{
  "id": 1,
  "status": "pending",
  "voice_id": 1,
  "input_text": "Hello, this is a test of voice cloning.",
  "created_at": "2024-01-01T12:00:00Z",
  "task_id": "abc123..."
}
```

#### Get Cloning Job Status

```bash
curl -X GET "http://localhost:8000/api/v1/voice/clone/1/status" \
     -H "Authorization: Bearer ${TOKEN}"
```

Response:

```json
{
  "job_id": 1,
  "status": "completed",
  "created_at": "2024-01-01T12:00:00Z",
  "completed_at": "2024-01-01T12:01:00Z",
  "output_url": "https://storage.example.com/output.wav",
  "task_status": {
    "state": "SUCCESS",
    "progress": 100,
    "error": null
  }
}
```

#### Retry Failed Job

```bash
curl -X POST "http://localhost:8000/api/v1/voice/clone/1/retry" \
     -H "Authorization: Bearer ${TOKEN}"
```

### Start Diarization Job

```curl -X POST "http://localhost:8000/api/v1/speaker/diarize" \
-H "Authorization: Bearer ${TOKEN}" \
-F "file=@audio.wav" \
-F "num_speakers=3" # Optional
```

#### Get Diarization Job Results

```bash
curl -X GET "http://localhost:8000/api/v1/speaker/jobs/1" \
     -H "Authorization: Bearer ${TOKEN}"
```

#### 2. Speaker Extraction

Uses `pyannote/speech-separation-ami-1.0` to separate different speakers into individual audio files.

```bash
# Start extraction job
curl -X POST "http://localhost:8000/api/v1/speaker/extract" \
-H "Authorization: Bearer ${TOKEN}" \
-F "file=@audio.wav"
```

#### Get Extraction Job Results

```bash
curl -X GET "http://localhost:8000/api/v1/speaker/jobs/1" \
     -H "Authorization: Bearer ${TOKEN}"
```

### Audio Translation

#### Create Translation Job

```bash
curl -X POST "http://localhost:8000/api/v1/translation/translate/" \
     -H "Authorization: Bearer ${TOKEN}" \
     -F "target_language=es" \
     -F "source_language=en" \
     -F "file=@/path/to/audio.wav"
```

Response:

```json
{
  "id": 1,
  "status": "pending",
  "source_language": "en",
  "target_language": "es",
  "created_at": "2024-01-01T12:00:00Z",
  "task_id": "xyz789..."
}
```

#### Translate from URL

```bash
curl -X POST "http://localhost:8000/api/v1/translation/translate/url/" \
     -H "Authorization: Bearer ${TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
           "url": "https://example.com/audio.mp3",
           "target_language": "es",
           "source_language": "en"
         }'
```

#### Get Translation Status

```bash
curl -X GET "http://localhost:8000/api/v1/translation/translations/1" \
     -H "Authorization: Bearer ${TOKEN}"
```

Response:

```json
{
  "id": 1,
  "status": "completed",
  "source_language": "en",
  "target_language": "es",
  "created_at": "2024-01-01T12:00:00Z",
  "completed_at": "2024-01-01T12:02:00Z",
  "output_url": "https://storage.example.com/translated.wav",
  "transcript_url": "https://storage.example.com/transcript.txt"
}
```

#### Batch Translation

```bash
curl -X POST "http://localhost:8000/api/v1/translation/translate/batch/" \
     -H "Authorization: Bearer ${TOKEN}" \
     -F "target_language=es" \
     -F "source_language=en" \
     -F "files[]=@/path/to/audio1.wav" \
     -F "files[]=@/path/to/audio2.wav"
```

### Health Check

#### Get API Status

```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

Response:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "gpu_available": true
}
```

### WebSocket Connection

```bash
# Using wscat for WebSocket testing
wscat -c "ws://localhost:8000/ws/${TOKEN}"
```

Example message:

```json
{
  "job_id": 1,
  "status": "processing",
  "progress": 50,
  "details": {
    "step": "generating_audio",
    "time_remaining": "30s"
  }
}
```

### Rate Limits

- Authentication endpoints: 5 requests per minute
- Voice cloning: 10 requests per minute
- Translation: 20 requests per minute
- Health check: 100 requests per minute

### Error Responses

Standard error response format:

```json
{
  "error_code": "INVALID_INPUT",
  "message": "Invalid input parameters",
  "details": {
    "field": "target_language",
    "error": "Unsupported language code"
  }
}
```

## Architecture

### Component Overview

```
audio-processing-api/
├── app/
│   ├── api/            # API endpoints
│   ├── core/           # Core functionality
│   ├── db/             # Database
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic schemas
│   ├── services/       # Business logic
│   └── workers/        # Celery tasks
```

### Key Components

- FastAPI for async API
- Celery for distributed task processing
- PostgreSQL for persistent storage
- Redis for caching and task queue
- S3 for file storage
- Prometheus/Grafana for monitoring

## Monitoring

### Available Metrics

- Request latency
- Queue lengths
- Job processing times
- Model inference times
- Resource usage (CPU, RAM, GPU)
- Error rates

### Prometheus Endpoints

```http
GET /metrics
```

### Grafana Dashboards

- API Performance
- Queue Statistics
- Resource Usage
- Error Tracking

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests and linters
4. Submit a pull request

See [Contributing Guide](CONTRIBUTING.md) for details.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Detailed Setup Guide

### 1. Initial Setup

The project includes several setup scripts in the `scripts/` directory to help with installation and configuration.

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run initial setup (dev or prod mode)
./scripts/setup.sh dev
```

The setup script will:

- Install Python dependencies using Poetry
- Download and verify AI models (XTTS-v2 and Whisper)
- Create necessary directories
- Set appropriate permissions

### 2. Database Migrations

Use the migration script to manage database schema:

```bash
# Run migrations
./scripts/migrate.sh

# For manual migration commands:
poetry run alembic revision --autogenerate -m "description"  # Create migration
poetry run alembic upgrade head                             # Apply migrations
poetry run alembic downgrade -1                            # Rollback one step
```

### 3. Starting Services

The start script provides flexible service management:

```bash
# Development mode
./scripts/start.sh start dev    # Start services
./scripts/start.sh stop         # Stop services
./scripts/start.sh restart dev  # Restart services

# Production mode
./scripts/start.sh start prod   # Start with production settings
```

The start script handles:

- Environment verification
- Redis service management
- Celery workers configuration
- FastAPI server startup
- GPU detection and configuration

### 4. Environment Configuration

Create and configure your environment variables:

```bash
# Copy example environment file
cp .env.example .env

# Edit required variables:
nano .env
```

Key environment variables:

```bash
# API Settings
DEBUG=true
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=your-secret-key

# Database
POSTGRES_SERVER=localhost
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=audio_processing

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# S3 Storage
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET=your_bucket
S3_REGION=your_region

# GPU Settings
CUDA_VISIBLE_DEVICES=0
DEVICE_STRATEGY=auto

# Worker Settings
WORKER_CONCURRENCY=4
VOICE_QUEUE_CONCURRENCY=2
TRANSLATION_QUEUE_CONCURRENCY=4
```

### 5. Development Workflow

1. Start development environment:

```bash
# Initial setup if not done
./scripts/setup.sh dev

# Start services in development mode
./scripts/start.sh start dev
```

2. Run tests:

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html
```

3. Code quality checks:

```bash
# Format code
poetry run black app tests
poetry run isort app tests

# Type checking
poetry run mypy app
```

### 6. Production Deployment

1. Setup production environment:

```bash
# Production setup
./scripts/setup.sh prod

# Configure SSL (if needed)
sudo certbot --nginx -d api.example.com

# Start services in production mode
./scripts/start.sh start prod
```

2. Monitor logs:

```bash
# API logs
tail -f logs/api.log

# Worker logs
tail -f logs/celery.log
```

3. Monitor metrics:

```bash
# Check Prometheus metrics
curl http://localhost:9090/metrics

# View in Grafana
open http://localhost:3000
```
