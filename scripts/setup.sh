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

# Function to verify XTTS files
verify_xtts_files() {
    local dir="$1"
    local files=("model.pth" "config.json" "vocab.json" "speakers.pth")
    
    for file in "${files[@]}"; do
        if [ ! -f "$dir/$file" ]; then
            print_error "Missing XTTS file: $file in $dir"
            return 1
        else
            print_status "Found $file"
        fi
    done
    return 0
}

# Function to setup models
setup_models() {
    print_status "Setting up AI models..."
    
    # Setup XTTS model
    XTTS_DIR="models/XTTS-v2"
    if [ ! -d "$XTTS_DIR" ] || ! verify_xtts_files "$XTTS_DIR"; then
        print_warning "XTTS-v2 model not found or incomplete. Setting up..."
        
        # Create directory
        mkdir -p "$XTTS_DIR"
        
        # Copy files from source if they exist
        if [ -d "models/XTTS-v2" ] && verify_xtts_files "models/XTTS-v2"; then
            cp models/XTTS-v2/* "$XTTS_DIR/"
            print_status "Copied XTTS files successfully"
        else
            print_error "Source XTTS files not found or incomplete"
            exit 1
        fi
    fi
    
    # Verify final setup
    verify_xtts_files "$XTTS_DIR" || {
        print_error "XTTS setup verification failed"
        exit 1
    }
    
    # Setup Whisper model
    WHISPER_DIR="models"
    if [ ! -d "$WHISPER_DIR" ] || [ ! -f "$WHISPER_DIR/model.bin" ]; then
        print_warning "Whisper model not found. Downloading..."
        mkdir -p "$WHISPER_DIR"
        
        # Download model files
        wget -q --show-progress https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/model.bin -O "$WHISPER_DIR/model.bin"
        wget -q --show-progress https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/config.json -O "$WHISPER_DIR/config.json"
        wget -q --show-progress https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/vocabulary.json -O "$WHISPER_DIR/vocabulary.json"
    fi
    
    # Set proper permissions
    chmod -R 755 models/
}

# Function to verify models
verify_models() {
    print_status "Verifying model files..."
    
    # Verify XTTS files
    for file in model.pth config.json vocab.json speakers.pth; do
        if [ ! -f "models/XTTS-v2/$file" ]; then
            print_error "Missing XTTS file: $file"
            return 1
        fi
    done
    
    # Verify Whisper files
    for file in model.bin config.json; do
        if [ ! -f "models/$file" ]; then
            print_error "Missing Whisper file: $file"
            return 1
        fi
    done
    
    print_status "All model files verified successfully"
    return 0
}

# Function to setup Python environment and dependencies
setup_python_env() {
    print_status "Setting up Python environment..."
    
    # Check if poetry is installed
    if ! command -v poetry &> /dev/null; then
        print_warning "Poetry not found. Installing..."
        curl -sSL https://install.python-poetry.org | python3 -
    fi
    
    # Install dependencies using Poetry
    if [ -f "pyproject.toml" ]; then
        print_status "Installing dependencies with Poetry..."
        
        # Check if lock file needs updating
        if ! poetry lock --check 2>/dev/null; then
            print_warning "Poetry lock file is out of sync. Updating..."
            poetry lock --no-update
        fi
        
        # Install dependencies
        poetry install --no-root
    elif [ -f "requirements.txt" ]; then
        # Fallback to pip if no pyproject.toml exists
        print_status "Installing dependencies with pip..."
        python3 -m pip install -r requirements.txt
    else
        print_error "No dependency files found (pyproject.toml or requirements.txt)"
        exit 1
    fi
}

# Main setup process
main() {
    print_status "Starting setup..."
    
    # Setup Python environment first
    setup_python_env
    
    # Then setup models
    setup_models
    verify_models || {
        print_error "Model verification failed"
        exit 1
    }
    
    print_status "Setup completed successfully"
}

# Run main function
main