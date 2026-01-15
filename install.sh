#!/bin/bash

# Vibe-Tools Installation Script for macOS/Linux

set -e

# Parse arguments
DESKTOP_MODE=false
for arg in "$@"; do
    case $arg in
        --desktop)
            DESKTOP_MODE=true
            shift
            ;;
    esac
done

echo "--- Installing Vibe-Tools ---"

# Check for Git
if ! command -v git &> /dev/null; then
    echo "⚠️  Warning: git is not installed. Git is required for vibe-tools."
    echo "   Please install Git: https://git-scm.com/"
fi

# Check for GitHub CLI
if ! command -v gh &> /dev/null; then
    echo "⚠️  Note: GitHub CLI (gh) is not installed. It is highly recommended for PR and issue integration."
    echo "   Install it via Homebrew: brew install gh"
fi

# Check for basic Python/pip presence first
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed. Please install Python first."
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed."
    exit 1
fi

# Helper to determine if we should use editable mode (-e)
# Default is standalone (not -e) unless config has standalone: false
get_install_flags() {
    local config_file="implementation/config.json"
    local standalone="true"
    
    if [[ -f "$config_file" ]]; then
        if command -v jq &> /dev/null; then
            standalone=$(jq -r '.setup.standalone // true' "$config_file")
        else
            # Fallback to python for JSON parsing
            standalone=$(python3 -c "import json, pathlib; p = pathlib.Path('$config_file'); print(str(json.loads(p.read_text()).get('setup', {}).get('standalone', True)).lower())" 2>/dev/null || echo "true")
        fi
    fi
    
    if [[ "$standalone" == "false" ]]; then
        echo "-e"
    else
        echo ""
    fi
}

INSTALL_FLAGS=$(get_install_flags)
if [[ -n "$INSTALL_FLAGS" ]]; then
    echo "💡 Using editable mode based on config (standalone: false)"
else
    echo "📦 Using standalone installation mode (default)"
fi

# Helper for global install
install_vibe_globally() {
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
        pipx install $INSTALL_FLAGS . --force
        echo "✅ Global installation via pipx complete."
    else
        # Fallback to older method if pipx unavailable
        if command -v pyenv &> /dev/null; then
            GLOBAL_PY=$(pyenv global | head -n 1)
            echo "Fallback: Installing to pyenv global ($GLOBAL_PY)..."
            pyenv exec pip install $INSTALL_FLAGS .
            pyenv rehash
        else
            echo "Fallback: Installing to system python..."
            python3 -m pip install $INSTALL_FLAGS .
        fi
    fi
}

# --- Desktop Application Build & Install ---
if [[ $DESKTOP_MODE == true ]]; then
    echo ""
    echo "🖥️  Entering Desktop Installation Mode"
    
    # 1. Dependency Checks for Desktop
    echo "Checking Node.js..."
    if ! command -v node &> /dev/null; then
        echo "Error: node is not installed. Node.js is required for the Tauri dashboard."
        exit 1
    fi
    
    echo "Checking Rust..."
    if ! command -v cargo &> /dev/null; then
        echo "Error: cargo (Rust) is not installed. Rust is required to build the Tauri dashboard."
        echo "Install it via: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
        exit 1
    fi

    # 2. Global Environment Setup
    echo "Initializing global environment..."
    python3 -m pip install $INSTALL_FLAGS .
    python3 -m vibe_tools.setup desktop-init

    # 3. Frontend Build
    echo "Building frontend assets..."
    cd frontend
    npm install
    npm run build
    cd ..

    # 4. Tauri Build
    echo "Building Tauri production bundle..."
    cd frontend
    # Generate icons if we have a source
    if [ -f "src-tauri/icons/icon.png" ]; then
        echo "Generating app icons from src-tauri/icons/icon.png..."
        npm run tauri icon src-tauri/icons/icon.png
    fi
    npm run tauri build
    cd ..

    # 5. App Installation (macOS only for now)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        APP_PATH=$(ls -d frontend/src-tauri/target/release/bundle/macos/*.app | head -n 1)
        if [[ -d "$APP_PATH" ]]; then
            echo ""
            read -p "Would you like to move the Vibe Dashboard to your Applications folder? (y/n): " move_app
            if [[ $move_app == "y" || $move_app == "Y" ]]; then
                echo "Installing to /Applications..."
                cp -R "$APP_PATH" /Applications/
                echo "✅ Vibe Dashboard installed in /Applications"
            fi
        fi
    fi

    echo ""
    echo "--- Desktop Installation Complete ---"
    exit 0
fi

# Standard (CLI-only) installation flow
# Option for global installation
echo "Do you want to install 'vibe' globally so it's available in all environments?"
echo "(Recommended: This uses 'pipx' to make commands available everywhere)"
read -p "(y/n): " install_global
if [[ $install_global == "y" || $install_global == "Y" ]]; then
    install_vibe_globally
fi

# Check if user wants managed environment
echo "Do you want to set up a project-specific managed Python environment (pyenv/virtualenv)?"
read -p "(y/n): " use_managed
if [[ $use_managed == "y" || $use_managed == "Y" ]]; then
    echo "Installing bootstrap dependencies..."
    python3 -m pip install $INSTALL_FLAGS .
    
    # Now run the env setup
    python3 -m vibe_tools.setup env
    echo ""
    echo "--- Managed Setup Complete ---"
    echo "Please restart your terminal or run 'eval \"\$(pyenv init -)\"' to activate the environment."
    exit 0
fi

# Standard installation if managed setup is skipped
echo "Installing package..."
python3 -m pip install $INSTALL_FLAGS .

echo ""
echo "--- Installation Complete ---"
echo "You can now use the 'vibe' and 'vibe-setup' commands."
echo "Try running: vibe --help or vibe-setup --help"
