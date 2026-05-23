@echo off
chcp 65001 >nul
echo ==========================================
echo   WelearnGUI - PyInstaller 打包脚本
echo ==========================================
echo.
echo 正在清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

echo.
echo 开始打包...
pyinstaller --clean --onefile --windowed --name WelearnGUI --collect-data customtkinter --hidden-import queue src\welearn_gui.py

echo.
echo ==========================================
echo  打包完成!
echo  输出文件: dist\WelearnGUI.exe
echo ==========================================
pause
