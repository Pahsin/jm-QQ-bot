@echo off
REM 打包 GUI 为独立 exe（用 PyInstaller）
REM 需要系统 Python（有 tkinter）+ 已安装 pyinstaller

chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Build QQ Manga Bot GUI to exe
echo ============================================
echo.

REM 使用系统 Python（带 tkinter）
set "SYS_PYTHON=C:\Users\lemon\AppData\Local\Microsoft\WindowsApps\python.exe"

REM 安装 pyinstaller
echo [1/3] Installing PyInstaller...
"%SYS_PYTHON%" -m pip install -U pyinstaller

REM 打包
echo [2/3] Building exe...
"%SYS_PYTHON%" -m PyInstaller --noconfirm --onefile --windowed --name "QQ漫画机器人" main.py

echo [3/3] Done!
echo.
echo Output: dist\QQ漫画机器人.exe
echo.
pause
