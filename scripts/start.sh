#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[-]${NC} $1"
}

# Function to verify required models
verify_models() {
    print_status "Verifying AI models..."
    
    # Check XTTS model
    XTTS_MODEL_DIR="models/XTTS-v2"
    if [ ! -f "$XTTS_MODEL_DIR/model.pth" ] || [ ! -f "$XTTS_MODEL_DIR/config.json" ] || [ ! -f "$XTTS_MODEL_DIR/vocab.json" ] || [ ! -f "$XTTS_MODEL_DIR/speakers.pth" ]; then
        print_warning "XTTS model files missing. Downloading..."
        poetry run tts --download_path=models/ --model_name="tts_models/multilingual/multi-dataset/xtts_v2"
        
        # Move downloaded files to XTTS-v2 directory
        mkdir -p "$XTTS_MODEL_DIR"
        mv models/XTTS-v2/* "$XTTS_MODEL_DIR/"
        rm -rf models/tts_models--multilingual--multi-dataset--xtts_v2
        
        # Verify download was successful
        if [ ! -f "$XTTS_MODEL_DIR/model.pth" ] || [ ! -f "$XTTS_MODEL_DIR/config.json" ]; then
            print_error "Failed to download XTTS model files"
            exit 1
        fi
    fi
    
    # Check Whisper model files
    WHISPER_MODEL_DIR="models"
    mkdir -p "$WHISPER_MODEL_DIR"
    
    if [ ! -f "$WHISPER_MODEL_DIR/model.bin" ] || [ ! -f "$WHISPER_MODEL_DIR/config.json" ]; then
        print_warning "Whisper model files missing. Downloading from Hugging Face..."
        
        # Download model.bin
        print_status "Downloading model.bin..."
        wget -q --show-progress https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/model.bin -O "$WHISPER_MODEL_DIR/model.bin"
        
        # Download config.json
        print_status "Downloading config.json..."
        wget -q --show-progress https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/config.json -O "$WHISPER_MODEL_DIR/config.json"
        
        if [ ! -f "$WHISPER_MODEL_DIR/model.bin" ] || [ ! -f "$WHISPER_MODEL_DIR/config.json" ]; then
            print_error "Failed to download Whisper model files"
            exit 1
        fi
    fi
    
    # Set proper permissions
    chmod -R 755 models/
}

# Function to check environment
check_env() {
    print_status "Checking environment..."
    
    if [ ! -f ".env" ]; then
        print_error ".env file not found"
        print_status "Creating from example..."
        cp .env.example .env || {
            print_error "Failed to create .env file"
            exit 1
        }
    fi
    
    # Install watchdog for development mode
    if [ "$1" = "dev" ]; then
        poetry run pip install watchdog[watchmedo]
    fi
}

# Function to check if service is running
check_service() {
    if ! pgrep -f "$1" > /dev/null; then
        return 1
    fi
    return 0
}

# Function to start Redis if not running
start_redis() {
    if ! check_service "redis-server"; then
        print_status "Starting Redis..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew services start redis || {
                print_error "Failed to start Redis"
                exit 1
            }
        else
            sudo service redis-server start || {
                print_error "Failed to start Redis"
                exit 1
            }
        fi
    else
        print_warning "Redis is already running"
    fi
}

# Function to start services
start_services() {
    local mode=$1
    
    # Create necessary directories
    mkdir -p logs
    mkdir -p data/uploads
    mkdir -p data/outputs
    mkdir -p data/transcripts
    
    # Set environment variables for GPU if available
    if python3.11 -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'" 2>/dev/null; then
        export CUDA_VISIBLE_DEVICES=0
        print_status "GPU support enabled"
    else
        print_warning "Running in CPU mode (not recommended for production)"
    fi
    
    if [ "$mode" = "dev" ]; then
        # Start services in development mode
        print_status "Starting services in development mode..."
        
        # Start Celery worker with auto-reload
        print_status "Starting Celery worker..."
        poetry run celery -A app.core.celery_app worker \
            --loglevel=info \
            -Q voice-queue,translation-queue \
            --concurrency=2 \
            --max-tasks-per-child=10 &
        
        # Start FastAPI with auto-reload
        print_status "Starting FastAPI server..."
        poetry run uvicorn app.main:app \
            --reload \
            --host 0.0.0.0 \
            --port 8000 \
            --log-level debug \
            --reload-dir app
            
    elif [ "$mode" = "prod" ]; then
        # Start services in production mode
        print_status "Starting services in production mode..."
        
        # Start Celery worker
        print_status "Starting Celery worker..."
        poetry run celery -A app.core.celery_app worker \
            --loglevel=info \
            -Q voice-queue,translation-queue \
            --concurrency=${WORKER_CONCURRENCY:-2} \
            --max-tasks-per-child=100 &
        
        # Start FastAPI with production settings
        print_status "Starting FastAPI server..."
        poetry run uvicorn app.main:app \
            --host 0.0.0.0 \
            --port ${PORT:-8000} \
            --workers ${WEB_CONCURRENCY:-4} \
            --log-level info \
            --proxy-headers \
            --forwarded-allow-ips='*'
            
    else
        print_error "Invalid mode. Use 'dev' or 'prod'"
        exit 1
    fi
}

# Function to stop services
stop_services() {
    print_status "Stopping services..."
    
    # Stop Celery workers
    pkill -f 'celery worker' || true
    
    # Stop uvicorn
    pkill -f 'uvicorn' || true
    
    # Stop Redis if running
    if check_service "redis-server"; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew services stop redis
        else
            sudo service redis-server stop
        fi
    fi
    
    print_status "All services stopped"
}

# Main function
main() {
    local command=$1
    local mode=$2
    
    case $command in
        "start")
            if [ -z "$mode" ]; then
                print_error "Please specify mode: dev or prod"
                exit 1
            fi
            verify_models
            check_env
            start_redis
            start_services "$mode"
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            if [ -z "$mode" ]; then
                print_error "Please specify mode: dev or prod"
                exit 1
            fi
            stop_services
            sleep 2
            verify_models
            check_env
            start_redis
            start_services "$mode"
            ;;
        *)
            print_error "Usage: $0 {start|stop|restart} {dev|prod}"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"