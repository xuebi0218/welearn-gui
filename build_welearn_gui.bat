@echo off
chcp 65001 >nul
echo ==========================================
echo   WelearnGUI - PyInstaller 打包脚本
echo ==========================================
echo.
echo 正在清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist\WelearnGUI.exe del /q dist\WelearnGUI.exe
if exist WelearnGUI.spec del /q WelearnGUI.spec

echo.
echo 开始打包...
pyinstaller --clean --onefile --windowed --name WelearnGUI ^
 --add-data "src/donate_qr.jpg;src/" --add-data "src/help_1.jpg;src/" ^
 --add-data "src/help_2.jpg;src/" --add-data "src/help_3.jpg;src/" ^
 --add-data "src/mascot.png;src/" --add-data "src/mascot_classic.png;src/" ^
 --add-data "src/strip.png;src/" --add-data "src/banner.png;src/" ^
 --add-data "src/anim_0.png;src/" --add-data "src/anim_1.png;src/" ^
 --add-data "src/anim_2.png;src/" --add-data "src/anim_3.png;src/" ^
 --add-data "src/anim_4.png;src/" --add-data "src/anim_5.png;src/" ^
 --collect-data customtkinter --hidden-import queue ^
 --hidden-import PIL --hidden-import PIL.Image --hidden-import brotli ^
 src\welearn_gui.py

echo.
echo ==========================================
echo  打包完成!
echo  输出文件: dist\WelearnGUI.exe
echo ==========================================
pause
