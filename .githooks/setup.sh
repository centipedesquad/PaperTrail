#!/bin/sh
# .githooks/setup.sh
#
# Activate project git hooks. Run once after cloning:
#   sh .githooks/setup.sh

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ]; then
    echo "Error: Not in a git repository."
    exit 1
fi

git config core.hooksPath .githooks
echo "Git hooks activated. Using .githooks/ directory."
echo ""
echo "Hooks installed:"
for hook in "$REPO_ROOT"/.githooks/pre-commit "$REPO_ROOT"/.githooks/commit-msg "$REPO_ROOT"/.githooks/pre-push; do
    if [ -f "$hook" ]; then
        echo "  - $(basename "$hook")"
    fi
done
echo ""
echo "To bypass hooks in an emergency: git commit --no-verify"
