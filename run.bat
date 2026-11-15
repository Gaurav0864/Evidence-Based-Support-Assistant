@echo off
cd /d "%~dp0"
python app.py --serve
if errorlevel 1 (
    echo.
    echo The app could not start. Check that Python is installed and available on PATH.
    pause
)
