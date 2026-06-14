@echo off
chcp 65001 >nul
title A股量化系统

cd /d "%~dp0"

echo.
echo ╔════════════════════════════════╗
echo ║     A股量化系统 启动中...      ║
echo ╚════════════════════════════════╝
echo.

echo [1/2] 检查环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python, 请先安装 Python 3.10+
    pause
    exit /b 1
)

echo [2/2] 启动服务...
python launcher.py

pause
