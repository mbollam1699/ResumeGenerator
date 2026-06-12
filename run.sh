#!/usr/bin/env bash
PYTHONPATH="$(dirname "$0")/.pkgs" python -m streamlit run "$(dirname "$0")/app.py"
