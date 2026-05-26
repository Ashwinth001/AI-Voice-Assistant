@echo off
setlocal enabledelayedexpansion
title ASTRA AI Assistant - Setup
color 0B

echo.
echo  =====================================================
echo  ^|       ASTRA v2.0 - AI Assistant Setup            ^|
echo  ^|  Advanced Self-Training Reasoning Assistant      ^|
echo  =====================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] ERROR: Python not found
    echo     Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo [OK] Python %%v found

:: Check for Groq API key (preferred) or Ollama
if defined GROQ_API_KEY (
    echo [OK] Groq API key found - using cloud LLM ^(fast^)
    set LLM_MODE=groq
) else (
    ollama --version >nul 2>&1
    if errorlevel 1 (
        echo [!] WARNING: Neither Groq API key nor Ollama found
        echo     For best experience, set GROQ_API_KEY environment variable
        echo     Get free key at: https://console.groq.com
        echo.
        echo     OR install Ollama from: https://ollama.com
        echo.
        set /p CONTINUE="Continue anyway? (y/n): "
        if /i "!CONTINUE!" neq "y" exit /b 1
    ) else (
        echo [OK] Ollama found - using local LLM
        set LLM_MODE=ollama
    )
)

:: Create directories
echo.
echo Creating directories...
if not exist assets mkdir assets
if not exist assets\voices mkdir assets\voices
if not exist data mkdir data
if not exist data\chroma mkdir data\chroma
if not exist data\training mkdir data\training
if not exist data\adapters mkdir data\adapters
if not exist data\users mkdir data\users
echo [OK] Directories ready

:: Install packages
echo.
echo Installing Python packages ^(this may take a few minutes^)...
pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
    echo [X] ERROR: Package installation failed
    echo     Try running: pip install -r requirements.txt
    pause
    exit /b 1
)
echo [OK] Packages installed

:: Pull Ollama model if using local LLM
if "%LLM_MODE%"=="ollama" (
    echo.
    echo Pulling LLM model...
    ollama pull phi3.5 >nul 2>&1
    if errorlevel 1 (
        echo [!] phi3.5 failed, trying gemma2:2b...
        ollama pull gemma2:2b >nul 2>&1
    )
    echo [OK] LLM model ready
)

:: Generate filler sounds
if not exist assets\hmm.wav (
    echo.
    echo Generating audio assets...
    python utils\generate_assets.py >nul 2>&1
)
echo [OK] Audio assets ready

:: Download Piper voice
if not exist assets\voices\en_US-amy-medium.onnx (
    echo.
    echo Downloading Piper TTS voice ^(~50MB^)...
    python utils\download_voice.py
) else (
    echo [OK] Piper voice ready
)

:: Setup scheduled tasks
echo.
echo Setting up automated tasks...

:: Model updater at 3 AM
schtasks /query /tn "ASTRA_ModelUpdate" >nul 2>&1
if errorlevel 1 (
    schtasks /create /tn "ASTRA_ModelUpdate" /tr "python \"%~dp0core\model_updater.py\"" /sc DAILY /st 03:00 /f >nul 2>&1
    if not errorlevel 1 echo [OK] Model updater scheduled ^(3 AM daily^)
)

:: Training at 2 AM every 2 days (Kaggle FREE GPU)
schtasks /query /tn "ASTRA_Training" >nul 2>&1
if errorlevel 1 (
    schtasks /create /tn "ASTRA_Training" /tr "python \"%~dp0training\kaggle_train.py\"" /sc DAILY /mo 2 /st 02:00 /f >nul 2>&1
    if not errorlevel 1 echo [OK] Training scheduled ^(Every 2 days - FREE Kaggle GPU^)
)

:: Add to startup (optional)
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if not exist "%STARTUP%\ASTRA.lnk" (
    echo.
    set /p AUTOSTART="Add ASTRA to Windows startup? (y/n): "
    if /i "!AUTOSTART!"=="y" (
        powershell -NoProfile -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%STARTUP%\ASTRA.lnk'); $Shortcut.TargetPath = '%~dp0run.bat'; $Shortcut.WorkingDirectory = '%~dp0'; $Shortcut.WindowStyle = 7; $Shortcut.Save()" >nul 2>&1
        if not errorlevel 1 echo [OK] Added to Windows startup
    )
)

echo.
echo  =====================================================
echo  ^|             ASTRA is ready!                      ^|
echo  =====================================================
echo.
echo  Configuration: config\config.yaml
echo  Wake word:     Say your AI name before each command
echo  Wake mode:     "always" ^(recommended^)
echo.
echo  Example commands (replace "nova" with your AI name):
echo    "Nova, open Chrome"
echo    "Nova, learn about machine learning"
echo    "Nova, remind me in 10 minutes to call John"
echo    "Nova, what's on my screen"
echo.
echo  Starting ASTRA...
echo  =====================================================
echo.

python main.py
if errorlevel 1 (
    echo.
    echo [X] ASTRA exited with an error
    echo     Check the error message above
    pause
)

endlocal
