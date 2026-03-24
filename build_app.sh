#!/bin/bash
# Build script for PaperTrail macOS application

set -e  # Exit on error

echo "================================"
echo "Building PaperTrail.app"
echo "================================"
echo ""

# Activate virtual environment
source .venv/bin/activate

# Clean previous builds
echo "1. Cleaning previous builds..."
rm -rf build dist
echo "   ✓ Cleaned"
echo ""

# Build the application
echo "2. Building application bundle with PyInstaller..."
pyinstaller --clean --noconfirm PaperTrail.spec
echo "   ✓ Built"
echo ""

# Verify the build
if [ -d "dist/PaperTrail.app" ]; then
    echo "3. Build verification..."
    echo "   ✓ Application bundle created: dist/PaperTrail.app"

    # Get bundle size
    SIZE=$(du -sh dist/PaperTrail.app | cut -f1)
    echo "   ✓ Bundle size: $SIZE"

    # Check if executable exists
    if [ -f "dist/PaperTrail.app/Contents/MacOS/PaperTrail" ]; then
        echo "   ✓ Executable found"
    else
        echo "   ✗ Executable not found"
        exit 1
    fi
    echo ""

    echo "================================"
    echo "✓ Build successful!"
    echo "================================"
    echo ""
    echo "To install:"
    echo "  cp -r dist/PaperTrail.app /Applications/"
    echo ""
    echo "Or drag dist/PaperTrail.app to your Applications folder"
    echo ""
    echo "To test before installing:"
    echo "  open dist/PaperTrail.app"
    echo ""
else
    echo "✗ Build failed: PaperTrail.app not found"
    exit 1
fi
