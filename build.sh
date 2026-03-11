#!/bin/bash
set -e

# Detect the correct backend directory
if [ -d "backend" ]; then
    BACKEND_DIR="backend"
elif [ -d "./backend" ]; then
    BACKEND_DIR="./backend"
elif [ -d "../backend" ]; then
    BACKEND_DIR="../backend"
else
    echo "Error: Could not find backend directory"
    echo "Current directory: $(pwd)"
    echo "Contents:"
    ls -la
    exit 1
fi

echo "Using backend directory: $BACKEND_DIR"
echo "Installing dependencies from $BACKEND_DIR/requirements.txt..."

# Install pdfplumber first with explicit version
pip install --no-cache-dir pdfplumber==0.11.9

# Install all requirements from backend
pip install --no-cache-dir -r "$BACKEND_DIR/requirements.txt"

echo "All dependencies installed successfully!"
exit 0

