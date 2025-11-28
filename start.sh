#!/bin/bash

# MIauCloudWeave - Proxmox API Startup Script
# This script starts the FastAPI server with proper configuration

set -e

echo "🚀 MIauCloudWeave - Proxmox API"
echo "================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your Proxmox configuration."
    echo ""
    read -p "Press Enter to continue or Ctrl+C to exit and configure .env first..."
fi

# Check Python version
echo "🐍 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python version: $python_version"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ Dependencies installed"

# Check Proxmox connection
echo ""
echo "🔍 Testing Proxmox connection..."
python3 -c "
from proxmox_client import test_connection
result = test_connection()
if result['success']:
    print(f\"✅ Connected to Proxmox v{result['version']}\")
else:
    print(f\"❌ Connection failed: {result.get('error', 'Unknown error')}\")
    print(\"⚠️  Please check your .env configuration\")
" || echo "⚠️  Could not test connection (will try again when server starts)"

echo ""
echo "🌐 Starting API server..."
echo "   URL: http://localhost:8001"
echo "   Docs: http://localhost:8001/docs"
echo "   ReDoc: http://localhost:8001/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
