@echo off
set PYTHONPATH=%~dp0.pkgs
python -m streamlit run "%~dp0app.py"
