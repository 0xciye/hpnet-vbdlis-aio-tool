@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0build_release.ps1"
if errorlevel 1 (
    echo Build failed. Read the error above. Existing releases were preserved.
    exit /b 1
)
echo Release verified successfully. See the new folder under release.
