#!/bin/bash

# Vibe-Tools Installation Script for macOS/Linux

set -e

echo "--- Installing Vibe-Tools ---"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

# Check for pip
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed."
    exit 1
fi

# Install the package in editable mode
echo "Installing package..."
pip3 install -e .

echo ""
echo "--- Installation Complete ---"
echo "You can now use the 'vibe' command."
echo "Try running: vibe --help"


