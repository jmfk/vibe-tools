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

# Option for global installation
echo "Do you want to install 'vibe' globally so it's available in all environments?"
echo "(Recommended: This uses 'pipx' to make commands available everywhere)"
read -p "(y/n): " install_global
if [[ $install_global == "y" || $install_global == "Y" ]]; then
    if ! command -v pipx &> /dev/null; then
        echo "pipx not found. pipx is recommended for global Python tools."
        if command -v brew &> /dev/null; then
            read -p "Install pipx via Homebrew? (y/n): " install_pipx
            if [[ $install_pipx == "y" || $install_pipx == "Y" ]]; then
                brew install pipx
                pipx ensurepath
                # We need to refresh PATH for the current script
                export PATH="$PATH:$HOME/.local/bin"
            fi
        else
            echo "Please install pipx first: https://pypa.github.io/pipx/"
        fi
    fi

    if command -v pipx &> /dev/null; then
        echo "Installing vibe-tools globally via pipx..."
        pipx install -e . --force
        echo "✅ Global installation via pipx complete."
    else
        # Fallback to older method if pipx unavailable
        if command -v pyenv &> /dev/null; then
            GLOBAL_PY=$(pyenv global | head -n 1)
            echo "Fallback: Installing to pyenv global ($GLOBAL_PY)..."
            pyenv exec pip install -e .
            pyenv rehash
        else
            echo "Fallback: Installing to system python..."
            python3 -m pip install -e .
        fi
    fi
fi

# Check if user wants managed environment
echo "Do you want to set up a project-specific managed Python environment (pyenv/virtualenv)?"
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



