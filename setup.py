"""
ASTRA Windows Installer
Creates EXE and adds to Windows startup.
Run: python setup.py build
"""
import sys
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def create_installer_script():
    """Create NSIS installer script."""
    nsis_script = '''
!include "MUI2.nsh"

Name "ASTRA AI Assistant"
OutFile "ASTRA-Setup.exe"
InstallDir "$PROGRAMFILES\\ASTRA"
RequestExecutionLevel admin

!define MUI_ICON "assets\\icon.ico"
!define MUI_UNICON "assets\\icon.ico"
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"
    
    ; Copy all files
    File /r "*.*"
    
    ; Create shortcuts
    CreateDirectory "$SMPROGRAMS\\ASTRA"
    CreateShortcut "$SMPROGRAMS\\ASTRA\\ASTRA.lnk" "$INSTDIR\\run.bat" "" "$INSTDIR\\assets\\icon.ico"
    CreateShortcut "$DESKTOP\\ASTRA.lnk" "$INSTDIR\\run.bat" "" "$INSTDIR\\assets\\icon.ico"
    
    ; Add to startup
    CreateShortcut "$SMSTARTUP\\ASTRA.lnk" "$INSTDIR\\run.bat" "" "$INSTDIR\\assets\\icon.ico"
    
    ; Create uninstaller
    WriteUninstaller "$INSTDIR\\uninstall.exe"
    
    ; Registry entries
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ASTRA" "DisplayName" "ASTRA AI Assistant"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ASTRA" "UninstallString" "$\\"$INSTDIR\\uninstall.exe$\\""
SectionEnd

Section "Uninstall"
    RMDir /r "$INSTDIR"
    RMDir /r "$SMPROGRAMS\\ASTRA"
    Delete "$DESKTOP\\ASTRA.lnk"
    Delete "$SMSTARTUP\\ASTRA.lnk"
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ASTRA"
SectionEnd
'''
    
    nsis_file = ROOT / "installer.nsi"
    nsis_file.write_text(nsis_script)
    print(f"[Installer] NSIS script created: {nsis_file}")
    return nsis_file


def create_startup_script():
    """Create script to add ASTRA to Windows startup."""
    startup_script = '''@echo off
echo Adding ASTRA to Windows startup...

set "ASTRA_PATH=%~dp0"
set "STARTUP=%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"

:: Create shortcut using PowerShell
powershell -NoProfile -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%STARTUP%\\ASTRA.lnk'); $Shortcut.TargetPath = '%ASTRA_PATH%run.bat'; $Shortcut.WorkingDirectory = '%ASTRA_PATH%'; $Shortcut.IconLocation = '%ASTRA_PATH%assets\\icon.ico'; $Shortcut.WindowStyle = 7; $Shortcut.Save()"

if exist "%STARTUP%\\ASTRA.lnk" (
    echo SUCCESS: ASTRA will now start automatically with Windows.
) else (
    echo WARNING: Could not create startup shortcut.
)

pause
'''
    
    script_file = ROOT / "add_to_startup.bat"
    script_file.write_text(startup_script)
    print(f"[Installer] Startup script created: {script_file}")


def create_first_run_launcher():
    """Create launcher that shows login on first run."""
    launcher_code = '''"""
ASTRA First Run Launcher
Shows login/register dialog on first run, then launches main app.
"""
import os
import sys
import json
import webbrowser
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config" / "config.yaml"
USER_FILE = ROOT / "data" / "user_session.json"


def is_first_run():
    """Check if this is first run (no user session)."""
    return not USER_FILE.exists()


def show_login_window():
    """Show login/register dialog."""
    root = tk.Tk()
    root.title("ASTRA Setup")
    root.geometry("400x300")
    root.configure(bg="#0f172a")
    root.resizable(False, False)
    
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 400) // 2
    y = (root.winfo_screenheight() - 300) // 2
    root.geometry(f"+{x}+{y}")
    
    # Title
    tk.Label(root, text="Welcome to ASTRA", font=("Arial", 18, "bold"),
             fg="#22d3ee", bg="#0f172a").pack(pady=20)
    
    tk.Label(root, text="Your AI assistant needs to be configured.",
             fg="#94a3b8", bg="#0f172a").pack()
    
    def open_register():
        webbrowser.open("http://localhost:8080/register")
        messagebox.showinfo("ASTRA", 
            "After registering, download your config.yaml and place it in the config folder.\\n\\n"
            "Then restart ASTRA.")
        root.destroy()
    
    def open_login():
        webbrowser.open("http://localhost:8080/login")
        messagebox.showinfo("ASTRA",
            "After logging in, download your config.yaml and place it in the config folder.\\n\\n"
            "Then restart ASTRA.")
        root.destroy()
    
    def skip_setup():
        # Create default user session
        USER_FILE.parent.mkdir(parents=True, exist_ok=True)
        USER_FILE.write_text(json.dumps({"user_id": "default", "configured": True}))
        root.destroy()
        launch_main()
    
    # Buttons
    btn_frame = tk.Frame(root, bg="#0f172a")
    btn_frame.pack(pady=30)
    
    tk.Button(btn_frame, text="Register (New User)", 
              command=open_register, width=20, height=2,
              bg="#0891b2", fg="white", relief="flat").pack(pady=5)
    
    tk.Button(btn_frame, text="Login (Existing User)",
              command=open_login, width=20, height=2,
              bg="#475569", fg="white", relief="flat").pack(pady=5)
    
    tk.Button(btn_frame, text="Skip (Use Defaults)",
              command=skip_setup, width=20, height=2,
              bg="#334155", fg="#94a3b8", relief="flat").pack(pady=5)
    
    root.mainloop()


def launch_main():
    """Launch main ASTRA application."""
    os.chdir(ROOT)
    os.system(f'"{sys.executable}" main.py')


def main():
    if is_first_run():
        show_login_window()
        if USER_FILE.exists():
            launch_main()
    else:
        launch_main()


if __name__ == "__main__":
    main()
'''
    
    launcher_file = ROOT / "launcher.py"
    launcher_file.write_text(launcher_code)
    print(f"[Installer] First-run launcher created: {launcher_file}")


def create_pyinstaller_spec():
    """Create PyInstaller spec file for EXE creation."""
    spec = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('core', 'core'),
        ('agents', 'agents'),
        ('ui', 'ui'),
        ('utils', 'utils'),
        ('training', 'training'),
        ('assets', 'assets'),
        ('web', 'web'),
        ('main.py', '.'),
        ('run.bat', '.'),
    ],
    hiddenimports=[
        'faster_whisper',
        'pyaudio',
        'webrtcvad',
        'chromadb',
        'pdfplumber',
        'pygame',
        'PIL',
        'gtts',
        'ollama',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ASTRA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
'''
    
    spec_file = ROOT / "astra.spec"
    spec_file.write_text(spec)
    print(f"[Installer] PyInstaller spec created: {spec_file}")


def build():
    """Build the installer."""
    print("=" * 60)
    print("  ASTRA Installer Builder")
    print("=" * 60)
    
    # Create scripts
    create_startup_script()
    create_first_run_launcher()
    create_pyinstaller_spec()
    create_installer_script()
    
    print("\n[Installer] Build files created. To create EXE:")
    print("  1. Install PyInstaller: pip install pyinstaller")
    print("  2. Run: pyinstaller astra.spec")
    print("  3. EXE will be in dist/ASTRA.exe")
    print("\nTo create full installer:")
    print("  1. Install NSIS: https://nsis.sourceforge.io/")
    print("  2. Run: makensis installer.nsi")
    print("=" * 60)


if __name__ == "__main__":
    build()
