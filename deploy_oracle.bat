@echo off
setlocal enabledelayedexpansion
title ASTRA - Oracle Cloud One-Click Deploy
color 0B
cd /d "%~dp0"

echo.
echo  =====================================================
echo  ^|   ASTRA - Oracle Cloud Deploy (Hyderabad)        ^|
echo  ^|   Region: ap-hyderabad-1                          ^|
echo  =====================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Optional: install oci CLI hint
where oci >nul 2>&1
if errorlevel 1 (
    echo [!] OCI CLI not in PATH.
    echo     Install: https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm
    echo     Then run: oci setup config
    echo.
)

echo [*] Starting deployment...
echo.

python cloud\deploy_oracle_oneclick.py %*
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% neq 0 (
    echo [X] Deploy finished with errors. See messages above.
) else (
    echo [+] Deploy script completed.
)
echo.
pause
exit /b %EXITCODE%
