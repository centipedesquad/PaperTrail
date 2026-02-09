#!/bin/bash
# Build script for myArXiv macOS application

set -e  # Exit on error

echo "================================"
echo "Building myArXiv.app"
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
pyinstaller --clean --noconfirm myarxiv.spec
echo "   ✓ Built"
echo ""

# Verify the build
if [ -d "dist/myArXiv.app" ]; then
    echo "3. Build verification..."
    echo "   ✓ Application bundle created: dist/myArXiv.app"

    # Get bundle size
    SIZE=$(du -sh dist/myArXiv.app | cut -f1)
    echo "   ✓ Bundle size: $SIZE"

    # Check if executable exists
    if [ -f "dist/myArXiv.app/Contents/MacOS/myArXiv" ]; then
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
    echo "  cp -r dist/myArXiv.app /Applications/"
    echo ""
    echo "Or drag dist/myArXiv.app to your Applications folder"
    echo ""
    echo "To test before installing:"
    echo "  open dist/myArXiv.app"
    echo ""
else
    echo "✗ Build failed: myArXiv.app not found"
    exit 1
fi
