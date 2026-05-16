@echo off
title IRONMARK — Quick Run
color 0A
echo.
echo  [IRONMARK] Запуск без сборки...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python не найден!
    pause
    exit /b 1
)

pip install customtkinter numpy psutil gputil pywin32 wmi --quiet
echo  [OK] Зависимости OK
echo.

python ironmark.py
