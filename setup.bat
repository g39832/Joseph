@echo off
echo ============================================
echo  JOSEPH AI Assistant - Phase 1 Setup
echo ============================================
echo.

REM Check Python version
python --version 2>NUL
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.12+ from https://python.org
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate

echo Installing Phase 1 dependencies...
pip install python-dotenv pydantic pydantic-settings ollama chromadb rich colorama requests aiofiles

echo.
echo Creating data directories...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "exports" mkdir exports

echo.
echo ============================================
echo  Setup Complete!
echo ============================================
echo.
echo Next steps:
echo   1. Make sure Ollama is running: ollama serve
echo   2. Pull the model: ollama pull llama3
echo   3. Run Joseph: python main.py
echo.
echo To activate venv in future sessions:
echo   venv\Scripts\activate
echo.
pause
