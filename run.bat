@echo off
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else if exist ai-app\Scripts\activate.bat (
    call ai-app\Scripts\activate.bat
)
python main.py
echo.
echo If the app did not show, check data\startup_log.txt for errors.
pause
