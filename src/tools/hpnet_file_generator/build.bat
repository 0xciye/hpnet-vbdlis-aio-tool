@echo off
echo Dang build ung dung HPNet Excel File Generator...

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

C:\Users\admin\AppData\Local\Programs\Python\Python312\python.exe -m PyInstaller --noconsole --name "HPNet Parcel Builder" --windowed main.py

echo Build hoan tat!
pause
