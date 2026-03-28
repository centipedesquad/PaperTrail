#!/bin/bash
# Build script for PaperTrail macOS application
# Usage: ./build_app.sh [--verbose]

set -e  # Exit on error

VERBOSE=false
if [ "$1" = "--verbose" ] || [ "$1" = "-v" ]; then
    VERBOSE=true
fi

# Progress bar helper
progress_bar() {
    local current=$1
    local total=$2
    local label=$3
    local width=30
    local filled=$((current * width / total))
    local empty=$((width - filled))
    printf "\r  [%s%s] %d/%d %s" \
        "$(printf '#%.0s' $(seq 1 $filled 2>/dev/null) 2>/dev/null)" \
        "$(printf '.%.0s' $(seq 1 $empty 2>/dev/null) 2>/dev/null)" \
        "$current" "$total" "$label"
}

cd "$(dirname "$0")"

echo "================================"
echo "Building PaperTrail.app"
echo "================================"
echo ""

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

    # Install dependencies (including build extras)
    echo "Installing dependencies..."
    python -m pip install ".[build]" || { echo "ERROR: Dependency installation failed."; exit 1; }
    echo ""
fi

# Ensure build dependencies are installed (handles the case where
# .venv exists but was set up with `pip install .` without build extras)
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing build dependencies (PyInstaller)..."
    if command -v uv &>/dev/null; then
        uv pip install ".[build]" || { echo "ERROR: Build dependency installation failed."; exit 1; }
    else
        python -m pip install ".[build]" || { echo "ERROR: Build dependency installation failed."; exit 1; }
    fi
fi

# Step 1: Clean
if $VERBOSE; then
    echo "1. Cleaning previous builds..."
    rm -rf build dist
    echo "   Done"
    echo ""
else
    progress_bar 1 3 "Cleaning previous builds..."
    rm -rf build dist
fi

# Step 2: Build
if $VERBOSE; then
    echo "2. Building application bundle with PyInstaller..."
    python -m PyInstaller --clean --noconfirm src/PaperTrail.spec
    echo "   Done"
    echo ""
else
    progress_bar 2 3 "Building with PyInstaller...  "
    python -m PyInstaller --clean --noconfirm src/PaperTrail.spec > /dev/null 2>&1
fi

# Step 3: Verify
if $VERBOSE; then
    echo "3. Build verification..."
fi

if [ -d "dist/PaperTrail.app" ]; then
    SIZE=$(du -sh dist/PaperTrail.app | cut -f1)

    if [ -f "dist/PaperTrail.app/Contents/MacOS/PaperTrail" ]; then
        if $VERBOSE; then
            echo "   Application bundle created: dist/PaperTrail.app"
            echo "   Bundle size: $SIZE"
            echo "   Executable found"
        else
            progress_bar 3 3 "Verified ($SIZE)               "
            echo ""
        fi
    else
        echo ""
        echo "Build failed: executable not found"
        exit 1
    fi

    echo ""
    echo "================================"
    echo "Build successful!"
    echo "================================"
    echo ""
    echo "To install:"
    echo "  cp -r dist/PaperTrail.app /Applications/"
    echo ""
    echo "Or drag dist/PaperTrail.app to your Applications folder"
    echo ""
    echo "If macOS Gatekeeper blocks the app (not notarized):"
    echo "  xattr -cr /Applications/PaperTrail.app"
    echo ""
    echo "To test before installing:"
    echo "  open dist/PaperTrail.app"
    echo ""
else
    echo ""
    echo "Build failed: PaperTrail.app not found"
    exit 1
fi
