#!/bin/bash
# Launcher script for PaperTrail application
set -e

cd "$(dirname "$0")"

# Activate virtual environment, or create one if missing
if [ -d ".venv" ] && [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "No local environment found — creating one automatically..."

    # Find system Python
    if command -v python3 &>/dev/null; then
        SYS_PYTHON=python3
    elif command -v python &>/dev/null; then
        SYS_PYTHON=python
    else
        echo "ERROR: No python3 or python found on this system."
        exit 1
    fi

    # Verify Python >= 3.10
    if ! $SYS_PYTHON -c "import sys; assert sys.version_info >= (3,10)" 2>/dev/null; then
        echo "ERROR: Python 3.10 or higher is required (found $($SYS_PYTHON --version 2>&1))."
        exit 1
    fi

    # Create virtual environment
    echo "Using $($SYS_PYTHON --version 2>&1) to create .venv..."
    if ! $SYS_PYTHON -m venv .venv; then
        echo "ERROR: Failed to create virtual environment."
        if [[ "$OSTYPE" == "linux"* ]]; then
            echo "On Debian/Ubuntu you may need: sudo apt install python3-venv"
        fi
        exit 1
    fi
    source .venv/bin/activate
    python -m pip install --upgrade pip --quiet

    # Install dependencies
    echo "Installing dependencies..."
    python -m pip install . || { echo "ERROR: Dependency installation failed."; exit 1; }
    echo ""
fi

cd src
python main.py "$@"
