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

echo "================================"
echo "Building PaperTrail.app"
echo "================================"
echo ""

# Activate virtual environment
source .venv/bin/activate

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
    pyinstaller --clean --noconfirm src/PaperTrail.spec
    echo "   Done"
    echo ""
else
    progress_bar 2 3 "Building with PyInstaller...  "
    pyinstaller --clean --noconfirm src/PaperTrail.spec > /dev/null 2>&1
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
