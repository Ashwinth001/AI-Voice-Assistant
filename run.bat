@echo off
echo ==========================================
echo  JARVIS - Setup and Launch
echo ==========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo PASS: Python found

ollama --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama not found
    echo Download: https://ollama.com
    pause
    exit /b 1
)
echo PASS: Ollama found

if not exist assets mkdir assets
if not exist assets\voices mkdir assets\voices
if not exist data mkdir data
if not exist data\chroma mkdir data\chroma
if not exist data\training mkdir data\training
if not exist data\adapters mkdir data\adapters
echo PASS: Folders ready

echo.
echo Installing packages...
pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
    echo ERROR: pip install failed
    pause
    exit /b 1
)
echo PASS: Packages installed

echo.
echo Pulling LLM model...
ollama pull phi3.5
if errorlevel 1 (
    echo WARNING: phi3.5 failed, trying gemma2:2b...
    ollama pull gemma2:2b
)
echo PASS: LLM model ready

if not exist assets\hmm.wav (
    echo Generating filler sound...
    python utils\generate_assets.py
)
echo PASS: Audio ready

if not exist assets\voices\en_US-amy-medium.onnx (
    echo Downloading Piper voice...
    python utils\download_voice.py
) else (
    echo PASS: Piper voice ready
)

echo.
echo ==========================================
echo  Ready - edit config\config.yaml to
echo  change name, wake word, model, theme
echo ==========================================
echo.
python main.py
if errorlevel 1 (
    echo.
    echo JARVIS exited with error - see above
    pause
)
