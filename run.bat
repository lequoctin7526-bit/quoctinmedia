@echo off
chcp 65001 > nul
title OmniMedia Pro - Web Tai Nhac & Video YouTube / Spotify

echo ========================================================
echo       Quoc Tin Media Pro - YouTube & Spotify Downloader
echo          Chat Luong Am Thanh Cao Nhat (320kbps)
echo ========================================================
echo.

set "PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if not exist "%PYTHON_PATH%" (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_PATH=python"
    ) else (
        echo [!] Khong tim thay Python 3.12!
        pause
        exit /b 1
    )
)

echo [*] Dang khoi dong may chu Web...
echo [*] Mo tren may tinh:   http://127.0.0.1:5500
echo [*] Mo tren dien thoai: http://192.168.50.130:5500 (cung mang Wi-Fi)
start http://127.0.0.1:5500
"%PYTHON_PATH%" app.py

pause
