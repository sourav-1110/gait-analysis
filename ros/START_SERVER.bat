@echo off
REM Gait Analysis Server - Quick Start Batch File
REM This script sets up and starts the Flask server

color 0A
cls

echo.
echo ================================================================
echo  Gait Analysis Flask Server - Quick Start
echo ================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Checking Python version
python --version
echo.

echo [2/4] Installing dependencies
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully
echo.

echo [3/4] Checking MongoDB
python -c "from pymongo import MongoClient; MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=3000).admin.command('ping'); print('MongoDB connection OK')" >nul 2>&1
if errorlevel 1 (
    echo WARNING: MongoDB not detected
    echo To start MongoDB on Windows:
    echo   1. Install from: https://www.mongodb.com/try/download/community
    echo   2. Run: mongod
    echo   3. Or use Docker: docker run -d -p 27017:27017 mongo:latest
    echo.
    set /p continue="Continue anyway? (y/n): "
    if /i not "%continue%"=="y" (
        exit /b 1
    )
) else (
    echo MongoDB connection OK
)
echo.

echo [4/4] Starting Flask Server
echo.
echo ================================================================
echo  Server Starting...
echo ================================================================
echo.
echo Dashboard:      http://localhost:5000/
echo Data View:      http://localhost:5000/data
echo API Health:     http://localhost:5000/health
echo.
echo Press Ctrl+C to stop the server
echo ================================================================
echo.

python app.py

pause
