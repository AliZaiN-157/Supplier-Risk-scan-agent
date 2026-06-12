@echo off
REM Run the Streamlit Dashboard (Windows)
REM Double-click this file or run: backend\run_streamlit.bat
REM Uses absolute path so it works from any directory.

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"
echo Starting Supplier Risk Scan Dashboard...
echo.
uv run --group dev streamlit run "%APP_DIR%streamlit_app.py" --server.port 8501
pause
