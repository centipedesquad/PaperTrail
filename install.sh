#!/bin/bash
# Install myArXiv to Applications folder

set -e

echo "================================"
echo "myArXiv Installer"
echo "================================"
echo ""

# Check if app exists
if [ ! -d "dist/myArXiv.app" ]; then
    echo "Error: dist/myArXiv.app not found"
    echo "Please build the application first using: ./build_app.sh"
    exit 1
fi

# Check if already installed
if [ -d "/Applications/myArXiv.app" ]; then
    echo "myArXiv is already installed in /Applications/"
    echo ""
    read -p "Do you want to replace it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi

    echo "Removing old version..."
    rm -rf /Applications/myArXiv.app
fi

# Install
echo "Installing myArXiv to /Applications/..."
cp -r dist/myArXiv.app /Applications/

# Verify
if [ -d "/Applications/myArXiv.app" ]; then
    echo ""
    echo "================================"
    echo "✓ Installation successful!"
    echo "================================"
    echo ""
    echo "myArXiv has been installed to /Applications/"
    echo ""
    echo "You can now:"
    echo "  • Launch it from Launchpad"
    echo "  • Search for it in Spotlight"
    echo "  • Open it from Applications folder"
    echo ""
    read -p "Do you want to launch it now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Launching myArXiv..."
        open /Applications/myArXiv.app
    fi
else
    echo "✗ Installation failed"
    exit 1
fi
