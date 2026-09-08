@echo off
echo Dang build ung dung HPNet Signed File Cleaner...

:: Create a clean build environment
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Run pyinstaller
python -m PyInstaller --noconsole --name "Signed PDF Cleaner" --icon "app_icon.ico" --add-data "app_icon.ico;." --windowed main.py

echo Build hoan tat!
pause
