@echo off
setlocal
cd /d "%~dp0"

set "VENV_DIR=.venv314"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%PYTHON%" (
  py -3.14 -m venv "%VENV_DIR%"
  if errorlevel 1 exit /b 1
)

"%PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 14) else 1)"
if errorlevel 1 (
  echo Build requires Python 3.14 in %VENV_DIR%.
  exit /b 1
)

"%PYTHON%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 exit /b 1

"%PYTHON%" tools\create_app_icon.py
if errorlevel 1 exit /b 1

"%PYTHON%" -m unittest discover -s tests -v
if errorlevel 1 exit /b 1

"%PYTHON%" tools\verify_ui.py
if errorlevel 1 exit /b 1

if exist "build\VBDLIS Excel Builder" rmdir /s /q "build\VBDLIS Excel Builder"
if exist "dist\VBDLIS Excel Builder" rmdir /s /q "dist\VBDLIS Excel Builder"

"%PYTHON%" -m PyInstaller --noconfirm --clean VBDLIS_Excel_Builder.spec
if errorlevel 1 exit /b 1

"%PYTHON%" tools\verify_build.py "dist\VBDLIS Excel Builder\VBDLIS Excel Builder.exe"
if errorlevel 1 exit /b 1

"%PYTHON%" tools\windows_file_icon.py "dist\VBDLIS Excel Builder\VBDLIS Excel Builder.exe" --refresh
if errorlevel 1 exit /b 1

echo Build PASS: dist\VBDLIS Excel Builder\VBDLIS Excel Builder.exe
endlocal
