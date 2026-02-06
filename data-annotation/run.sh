#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
APP_FILE="$SCRIPT_DIR/src/app.py"

# Ensure uv is available
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    uv venv "$VENV_DIR"
fi

# Install deps
echo "Installing dependencies..."
uv pip install --python "$VENV_DIR/bin/python" -r "$REQ_FILE"

# Launch
echo "Starting BanglaBias Annotation Tool..."
"$VENV_DIR/bin/streamlit" run "$APP_FILE" --server.port 8501 --server.headless true
