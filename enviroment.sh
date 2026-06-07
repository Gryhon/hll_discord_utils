#!/bin/bash

VENV_NAME="venv"
FORCE=false

for arg in "$@"; do
    if [ "$arg" = "--force" ] || [ "$arg" = "-f" ]; then
        FORCE=true
    fi
done

if [ "$FORCE" = true ]; then
    echo "Force mode: removing existing virtual environment..."
    rm -rf "$VENV_NAME"
fi

if [ -f .python-version ]; then
    PY_VERSION=$(cat .python-version)

    # Prüfe, ob die Version bereits installiert ist
    if pyenv versions --bare | grep -qx "$PY_VERSION"; then
        echo "Python $PY_VERSION is already installed."
    else
        echo "Installing Python $PY_VERSION..."
        pyenv install "$PY_VERSION"
    fi
else
    echo "No .python-version file found, skipping pyenv."
fi


# Check if Python3 and venv are installed
if ! command -v python3 &> /dev/null || ! python3 -m venv --help &> /dev/null; then
    echo "Python3 or the venv module is not installed."
    exit 1
fi

# Create the virtual environment
if [ ! -d "$VENV_NAME" ]; then
    python3 -m venv "$VENV_NAME"
    echo "Virtual environment '$VENV_NAME' has been created."
else
    echo "Virtual environment '$VENV_NAME' already exists, skipping creation. Use --force to recreate."
fi

# Activate the virtual environment
echo "Activating the virtual environment..."
source "./$VENV_NAME/bin/activate"

# Confirm that the environment is activated
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "The virtual environment '$VENV_NAME' is now activated."

    # Check if requirements.txt exists and install packages
    if [ -f "requirements.txt" ]; then
        echo "Installing required packages from requirements.txt..."
        pip install --upgrade pip
        pip install pytest
        pip install -r requirements.txt
        echo "Packages installed successfully."
    else
        echo "No requirements.txt file found. Skipping package installation."
    fi
else
    echo "Error activating the virtual environment."
fi

python3 --version

