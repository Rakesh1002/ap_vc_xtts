#!/bin/bash
set -e

echo "Installing system dependencies..."

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux (Ubuntu/Debian)
    sudo apt-get update
    sudo apt-get install -y \
        build-essential \
        automake \
        autoconf \
        libtool \
        pkg-config \
        python3-dev \
        ffmpeg \
        libsndfile1 \
        sox \
        libsox-dev \
        portaudio19-dev \
        libasound2-dev \
        cmake

elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if ! command -v brew &> /dev/null; then
        echo "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    brew install \
        automake \
        autoconf \
        libtool \
        pkg-config \
        ffmpeg \
        sox \
        portaudio \
        cmake

else
    echo "Unsupported operating system: $OSTYPE"
    exit 1
fi

echo "System dependencies installed successfully!" 