# Gait Analysis Server - Quick Start PowerShell Script
# This script sets up and starts the Flask server

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Gait Analysis Flask Server - Quick Start" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/4] Checking Python version" -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>$null
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://www.python.org/" -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host "[2/4] Installing dependencies" -ForegroundColor Yellow
try {
    python -m pip install -q -r requirements.txt
    Write-Host "Dependencies installed successfully" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Check MongoDB
Write-Host "[3/4] Checking MongoDB connection" -ForegroundColor Yellow
try {
    $result = python -c "from pymongo import MongoClient; MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=3000).admin.command('ping'); print('OK')" 2>$null
    if ($result -eq "OK") {
        Write-Host "MongoDB connection: OK" -ForegroundColor Green
    } else {
        throw "Connection failed"
    }
} catch {
    Write-Host "WARNING: MongoDB not detected" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To start MongoDB:" -ForegroundColor Cyan
    Write-Host "  - Windows: mongod" -ForegroundColor Gray
    Write-Host "  - Docker: docker run -d -p 27017:27017 mongo:latest" -ForegroundColor Gray
    Write-Host ""
    
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") {
        exit 1
    }
}

Write-Host ""

# Start server
Write-Host "[4/4] Starting Flask Server" -ForegroundColor Yellow
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Server Starting..." -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Dashboard:     http://localhost:5000/" -ForegroundColor Cyan
Write-Host "Data View:     http://localhost:5000/data" -ForegroundColor Cyan
Write-Host "API Health:    http://localhost:5000/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

python app.py

Write-Host ""
Write-Host "Server stopped" -ForegroundColor Yellow
