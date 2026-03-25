#!/bin/bash
# Install PaperTrail to Applications folder

set -e

echo "================================"
echo "PaperTrail Installer"
echo "================================"
echo ""

# Check if app exists
if [ ! -d "dist/PaperTrail.app" ]; then
    echo "Error: dist/PaperTrail.app not found"
    echo "Please build the application first using: ./build_app.sh"
    exit 1
fi

# Check if already installed
if [ -d "/Applications/PaperTrail.app" ]; then
    echo "PaperTrail is already installed in /Applications/"
    echo ""
    read -p "Do you want to replace it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi

    echo "Removing old version..."
    rm -rf /Applications/PaperTrail.app
fi

# Install
echo "Installing PaperTrail to /Applications/..."
cp -r dist/PaperTrail.app /Applications/

# Verify
if [ -d "/Applications/PaperTrail.app" ]; then
    echo ""
    echo "================================"
    echo "✓ Installation successful!"
    echo "================================"
    echo ""
    echo "PaperTrail has been installed to /Applications/"
    echo ""
    echo "You can now:"
    echo "  • Launch it from Launchpad"
    echo "  • Search for it in Spotlight"
    echo "  • Open it from Applications folder"
    echo ""
    read -p "Do you want to launch it now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Launching PaperTrail..."
        open /Applications/PaperTrail.app
    fi
else
    echo "✗ Installation failed"
    exit 1
fi
