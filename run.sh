#!/bin/bash
# Launcher script for myArXiv application

cd "$(dirname "$0")"
source .venv/bin/activate
cd src
python main.py "$@"
