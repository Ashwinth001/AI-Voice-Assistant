@echo off
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else if exist ai-app\Scripts\activate.bat (
    call ai-app\Scripts\activate.bat
)
echo Running tests...
python -m unittest discover -s tests -p "test_*.py" -v
pause
