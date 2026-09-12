@echo off
echo Dang build ung dung HPNet Excel File Generator...

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --noconsole --name "VBDLIS - Đặt tên hồ sơ" --icon "assets\app_icon.ico" --add-data "assets\app_icon.ico;assets" --windowed main.py

echo Build hoan tat!
pause
