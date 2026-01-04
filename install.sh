#!/bin/bash

# Vibe-Tools Installation Script for macOS/Linux

set -e

echo "--- Installing Vibe-Tools ---"

# Check for basic Python/pip presence first
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed. Please install Python first."
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed."
    exit 1
fi

# Check if user wants managed environment
echo "Do you want to set up a managed Python environment (pyenv/virtualenv)?"
read -p "(y/n): " use_managed
if [[ $use_managed == "y" || $use_managed == "Y" ]]; then
    echo "Installing bootstrap dependencies..."
    python3 -m pip install -e .
    
    # Now run the env setup
    python3 -m vibe_tools.setup env
    echo ""
    echo "--- Managed Setup Complete ---"
    echo "Please restart your terminal or run 'eval \"\$(pyenv init -)\"' to activate the environment."
    exit 0
fi

# Standard installation if managed setup is skipped
echo "Installing package..."
python3 -m pip install -e .

echo ""
echo "--- Installation Complete ---"
echo "You can now use the 'vibe' and 'vibe-setup' commands."
echo "Try running: vibe --help or vibe-setup --help"



