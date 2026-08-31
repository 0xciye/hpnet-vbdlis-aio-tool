@echo off
echo Dang build ung dung HPNet Signed File Cleaner...

:: Create a clean build environment
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Run pyinstaller
C:\Users\admin\AppData\Local\Programs\Python\Python312\python.exe -m PyInstaller --noconsole --name "Signed PDF Cleaner" --icon "icon.ico" --add-data "icon.ico;." --windowed main.py

echo Build hoan tat!
pause
