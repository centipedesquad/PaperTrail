#!/bin/bash
# Launcher script for PaperTrail application

cd "$(dirname "$0")"
source .venv/bin/activate
cd src
python main.py "$@"
