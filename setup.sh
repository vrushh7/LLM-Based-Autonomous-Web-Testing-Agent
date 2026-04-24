#!/bin/bash

# AI Testing Agent Setup Script
# This script helps set up the development environment

set -e  # Exit on error

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║     AI-Powered Autonomous Testing Agent Setup            ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo "→ Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Found Python $python_version"

# Check if Python version is 3.9 or higher
if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "  ✗ Error: Python 3.9 or higher is required"
    exit 1
fi
echo "  ✓ Python version is compatible"
echo ""

# Install Python dependencies
echo "→ Installing Python dependencies..."
cd backend
pip install -r requirements.txt
echo "  ✓ Python dependencies installed"
echo ""

# Install Playwright browsers
echo "→ Installing Playwright browsers..."
playwright install chromium
echo "  ✓ Playwright browsers installed"
echo ""

# Check if Ollama is installed
echo "→ Checking for Ollama installation..."
if command -v ollama &> /dev/null; then
    echo "  ✓ Ollama is installed"
    
    # Check if llama3 model is available
    echo "→ Checking for LLaMA-3 model..."
    if ollama list | grep -q "llama3"; then
        echo "  ✓ LLaMA-3 model is installed"
    else
        echo "  ⚠ LLaMA-3 model not found"
        read -p "  Would you like to download it now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ollama pull llama3
            echo "  ✓ LLaMA-3 model downloaded"
        else
            echo "  ⚠ Skipping model download. You'll need to run 'ollama pull llama3' later"
        fi
    fi
else
    echo "  ✗ Ollama not found"
    echo ""
    echo "  Please install Ollama from: https://ollama.ai/download"
    echo "  After installation, run: ollama pull llama3"
    echo ""
    exit 1
fi
echo ""

# Create necessary directories
echo "→ Creating directories..."
cd ..
mkdir -p backend/screenshots
mkdir -p backend/reports
echo "  ✓ Directories created"
echo ""

# Setup complete
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║              Setup completed successfully! ✓             ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Start the backend server:"
echo "   cd backend"
echo "   python main.py"
echo ""
echo "2. In a new terminal, start the frontend:"
echo "   cd frontend"
echo "   python -m http.server 8080"
echo ""
echo "3. Open your browser:"
echo "   http://localhost:8080"
echo ""
echo "4. Make sure Ollama is running:"
echo "   ollama serve"
echo ""
echo "For more information, see README.md and docs/DEVELOPMENT.md"
echo ""
