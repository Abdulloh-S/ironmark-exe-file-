@echo off
title IRONMARK — Build Script
color 0A
echo.
echo  ██ IRONMARK Build Script ██
echo  ============================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python не найден! Установи Python 3.10+ с python.org
    pause
    exit /b 1
)

echo  [1/4] Установка зависимостей...
pip install customtkinter numpy psutil gputil pywin32 wmi pyinstaller --quiet
if errorlevel 1 (
    echo  [ERROR] Ошибка установки зависимостей
    pause
    exit /b 1
)
echo  [OK] Зависимости установлены

echo.
echo  [2/4] Сборка EXE через PyInstaller...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "IRONMARK" ^
  --icon=icon.ico ^
  --add-data "icon.ico;." ^
  --hidden-import customtkinter ^
  --hidden-import numpy ^
  --hidden-import psutil ^
  --hidden-import wmi ^
  --hidden-import win32api ^
  --hidden-import win32con ^
  --hidden-import pywintypes ^
  --hidden-import GPUtil ^
  --collect-all customtkinter ^
  --clean ^
  ironmark.py

if errorlevel 1 (
    echo  [ERROR] Ошибка сборки!
    pause
    exit /b 1
)

echo.
echo  [3/4] Копирование EXE...
if exist "dist\IRONMARK.exe" (
    copy "dist\IRONMARK.exe" "IRONMARK.exe" >nul
    echo  [OK] IRONMARK.exe готов в текущей папке!
) else (
    echo  [ERROR] EXE не найден в dist\
    pause
    exit /b 1
)

echo.
echo  [4/4] Очистка временных файлов...
rmdir /s /q build >nul 2>&1
rmdir /s /q dist  >nul 2>&1
del *.spec        >nul 2>&1
echo  [OK] Очищено

echo.
echo  ============================================
echo   ГОТОВО! Запусти IRONMARK.exe
echo  ============================================
echo.
pause
