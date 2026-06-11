@echo off
title Gait Analysis Server

:: Try common Python locations
set PYTHON=
for %%P in (python python3) do (
    where %%P >nul 2>&1 && set PYTHON=%%P && goto :found
)
:: Try common install paths
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
) do (
    if exist %%P set PYTHON=%%P && goto :found
)

echo ERROR: Python not found. 
echo Please install Python from https://www.python.org/downloads/
echo Make sure to tick "Add Python to PATH" during install.
pause
exit /b 1

:found
echo Found Python: %PYTHON%
echo.

:: Go to project root (one level up from ros\)
cd /d "%~dp0.."
echo Project root: %CD%
echo.

:: Install Flask if needed
%PYTHON% -c "import flask" 2>nul || (
    echo Installing Flask...
    %PYTHON% -m pip install flask
)

:: Run the server from the ros folder
echo Starting server...
%PYTHON% ros\flask_server.py
pause
