#!/bin/bash
# Bump version number across all files that reference it.
# Usage: ./bump_version.sh <new-version>
# Example: ./bump_version.sh 0.7.0

set -e

cd "$(dirname "$0")"

# Cross-platform sed -i (BSD vs GNU)
sed_inplace() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

if [ -z "$1" ]; then
    echo "Usage: ./bump_version.sh <new-version>"
    echo "Example: ./bump_version.sh 0.7.0"
    echo ""
    # Show current version from pyproject.toml
    CURRENT=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
    echo "Current version: $CURRENT"
    exit 1
fi

NEW_VERSION="$1"

# Validate format (digits.digits.digits)
if ! echo "$NEW_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "ERROR: Version must be in X.Y.Z format (e.g., 0.7.0)"
    exit 1
fi

CURRENT=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
echo "Bumping version: $CURRENT -> $NEW_VERSION"
echo ""

# 1. pyproject.toml
if [ -f "pyproject.toml" ]; then
    sed_inplace "s/^version = \"$CURRENT\"/version = \"$NEW_VERSION\"/" pyproject.toml
    if grep -q "version = \"$NEW_VERSION\"" pyproject.toml; then
        echo "  Updated pyproject.toml"
    else
        echo "  WARNING: pyproject.toml was not updated (pattern not found)"
    fi
fi

# 2. src/ui/main_window.py
if [ -f "src/ui/main_window.py" ]; then
    sed_inplace "s/Version $CURRENT/Version $NEW_VERSION/" src/ui/main_window.py
    if grep -q "Version $NEW_VERSION" src/ui/main_window.py; then
        echo "  Updated src/ui/main_window.py"
    else
        echo "  WARNING: src/ui/main_window.py was not updated (pattern not found)"
    fi
fi

# 3. BUILDING.md
if [ -f "BUILDING.md" ]; then
    sed_inplace "s/\*\*Version\*\*: [0-9]*\.[0-9]*\.[0-9]*/\*\*Version\*\*: $NEW_VERSION/" BUILDING.md
    sed_inplace "s/PaperTrail-[0-9]*\.[0-9]*\.[0-9]*\.dmg/PaperTrail-$NEW_VERSION.dmg/" BUILDING.md
    if grep -q "$NEW_VERSION" BUILDING.md; then
        echo "  Updated BUILDING.md"
    else
        echo "  WARNING: BUILDING.md was not updated (pattern not found)"
    fi
fi

echo ""
echo "Done. If you use uv, run 'uv lock' to update uv.lock."
echo "Verify with: grep -rn '$NEW_VERSION' pyproject.toml src/ui/main_window.py BUILDING.md"
