# Audio Processing API

A high-performance audio processing service providing voice cloning and translation capabilities using state-of-the-art AI models (XTTS V2 and Faster Whisper).

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

### Technical Stack

- FastAPI 0.109.0 for async API
- PyTorch 2.1.2 with CUDA support
- PostgreSQL (Neon) with asyncpg
- Redis 5.0+ for caching and task queue
- Celery 5.3.6 for distributed processing
- S3-compatible storage
- Prometheus/Grafana monitoring
- JWT authentication and rate limiting

## Prerequisites

### System Requirements

- Python 3.11 (required)
- CUDA-capable GPU (recommended)
- FFmpeg
- PostgreSQL client
- Redis

### Installation

1. System Dependencies:

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y \
    python3.11 \
    python3.11-dev \
    ffmpeg \
    libpq-dev \
    postgresql-client \
    libsndfile1 \
    sox \
    libsox-dev \
    portaudio19-dev \
    libasound2-dev \
    cmake \
    pkg-config

# macOS
brew install \
    python@3.11 \
    ffmpeg \
    postgresql@14 \
    sox \
    portaudio \
    cmake \
    pkg-config
```

2. Clone and Setup:

```bash
# Clone repository
git clone https://github.com/yourusername/audio-processing-api
cd audio-processing-api

# Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh --dev  # Use --dev for development environment
```

3. Environment Configuration:

```bash
cp .env.example .env
# Edit .env with your settings
```

4. Start Services:

```bash
# Using Docker Compose
docker-compose up -d

# Or start components individually
docker-compose up -d db redis
poetry run uvicorn app.main:app --reload
poetry run celery -A app.core.celery_app worker -Q voice-queue,translation-queue
```

## Development

### Database Migrations

```bash
# Create new migration
poetry run alembic revision --autogenerate -m "Description"

# Apply migrations
poetry run alembic upgrade head

# Rollback
poetry run alembic downgrade -1
```

### Code Style

```bash
# Format code
poetry run black app tests

# Sort imports
poetry run isort app tests

# Type checking
poetry run mypy app
```

### Testing

```bash
# Run tests
poetry run pytest

# With coverage
poetry run pytest --cov=app --cov-report=html
```

## API Usage

### Authentication

```bash
# Register
curl -X POST "http://localhost:8000/api/v1/auth/register" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "password"}'

# Get token
curl -X POST "http://localhost:8000/api/v1/auth/token" \
     -d "username=user@example.com&password=password"
```

### Voice Cloning

```bash
# Upload voice
curl -X POST "http://localhost:8000/api/v1/voice/voices/" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@sample.wav" \
     -F "name=Test Voice"

# Create cloning job
curl -X POST "http://localhost:8000/api/v1/voice/clone/" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"voice_id": 1, "text": "Hello world"}'
```

### Translation

```bash
# Translate audio
curl -X POST "http://localhost:8000/api/v1/translation/translate/" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@audio.wav" \
     -F "target_language=es"

# Translate from URL
curl -X POST "http://localhost:8000/api/v1/translation/translate/url/" \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"url": "https://example.com/audio.mp3", "target_language": "es"}'
```

## Project Structure

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
├── scripts/           # Setup scripts
├── tests/            # Test suite
├── alembic/          # Database migrations
└── docs/             # Documentation
```

## Monitoring

- Prometheus metrics: `http://localhost:9090/metrics`
- API documentation: `http://localhost:8000/docs`
- OpenAPI spec: `http://localhost:8000/openapi.json`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests and linters
4. Submit a pull request

See [Contributing Guide](CONTRIBUTING.md) for details.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [XTTS V2](https://github.com/coqui-ai/TTS) - Coqui TTS
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper)
- [FastAPI](https://fastapi.tiangolo.com/)

## Running the Application

### Development Mode

```bash
# Start all services in development mode
chmod +x scripts/start.sh
./scripts/start.sh start dev
```

Development mode features:
- Auto-reload for code changes
- Debug logging
- 2 Celery workers
- Single uvicorn worker

### Production Mode

```bash
# Start all services in production mode
./scripts/start.sh start prod
```

Production mode features:
- Multiple uvicorn workers (configurable)
- Optimized Celery settings
- Production-level logging
- SSL/TLS support
- Proxy headers handling

### Environment Variables

Production deployment requires setting these environment variables:

```bash
# Web Server
PORT=8000                     # API port
WEB_CONCURRENCY=4            # Number of uvicorn workers
WORKER_CONCURRENCY=4         # Number of Celery workers

# GPU Settings
CUDA_VISIBLE_DEVICES=0,1     # Comma-separated GPU indices
DEVICE_STRATEGY=auto         # auto/cpu/cuda

# Security
ALLOWED_HOSTS=example.com    # Comma-separated hosts
CORS_ORIGINS=*              # CORS origins
```

### Service Management

```bash
# Start services
./scripts/start.sh start [dev|prod]

# Stop all services
./scripts/start.sh stop

# Restart services
./scripts/start.sh restart [dev|prod]
```

## Production Deployment

### System Requirements

- 8+ CPU cores
- 16GB+ RAM
- NVIDIA GPU with 8GB+ VRAM (recommended)
- 100GB+ SSD storage
- Ubuntu 20.04 LTS or newer

### Installation Steps

1. System Setup:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    nginx \
    redis-server \
    supervisor \
    ffmpeg \
    libpq-dev \
    postgresql-client \
    libsndfile1 \
    sox \
    libsox-dev \
    portaudio19-dev \
    libasound2-dev \
    cmake \
    pkg-config
```

2. NVIDIA Setup (if using GPU):

```bash
# Install NVIDIA drivers
sudo ubuntu-drivers autoinstall

# Install CUDA toolkit
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run
sudo sh cuda_11.8.0_520.61.05_linux.run
```

3. Application Setup:

```bash
# Clone repository
git clone https://github.com/yourusername/audio-processing-api
cd audio-processing-api

# Setup application
./scripts/setup.sh

# Configure environment
cp .env.example .env
nano .env
```

4. Nginx Configuration:

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

5. Supervisor Configuration:

```ini
[program:api]
command=/path/to/audio-processing-api/scripts/start.sh start prod
directory=/path/to/audio-processing-api
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/api.err.log
stdout_logfile=/var/log/supervisor/api.out.log
environment=
    PATH="/path/to/audio-processing-api/.venv/bin:%(ENV_PATH)s",
    CUDA_VISIBLE_DEVICES="0"

[program:celery]
command=/path/to/audio-processing-api/.venv/bin/celery -A app.core.celery_app worker --loglevel=info
directory=/path/to/audio-processing-api
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/celery.err.log
stdout_logfile=/var/log/supervisor/celery.out.log
environment=
    PATH="/path/to/audio-processing-api/.venv/bin:%(ENV_PATH)s",
    CUDA_VISIBLE_DEVICES="0"
```

6. Start Services:

```bash
# Start supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all

# Start nginx
sudo systemctl start nginx
```

### Monitoring

1. Check service status:
```bash
sudo supervisorctl status
```

2. View logs:
```bash
# API logs
tail -f /var/log/supervisor/api.out.log

# Celery logs
tail -f /var/log/supervisor/celery.out.log
```

3. Monitor resources:
```bash
# GPU usage
nvidia-smi -l 1

# System resources
htop
```

### Backup and Maintenance

1. Database backup:
```bash
# Backup database
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME > backup.sql

# Restore database
psql -h $DB_HOST -U $DB_USER -d $DB_NAME < backup.sql
```

2. Model files backup:
```bash
# Backup models directory
tar -czf models_backup.tar.gz models/
```

### Security Recommendations

1. Enable SSL/TLS with Let's Encrypt
2. Configure firewall (UFW)
3. Set up fail2ban
4. Regular security updates
5. Implement rate limiting
6. Use strong passwords and key-based SSH authentication
