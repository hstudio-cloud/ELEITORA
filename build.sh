#!/bin/bash
set -e

echo "Installing backend dependencies..."
cd backend
pip install --no-cache-dir pdfplumber==0.11.9
pip install --no-cache-dir -r requirements.txt

echo "Dependencies installed successfully!"
cd ..
