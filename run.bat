@echo off
chcp 65001 > nul
title OmniMedia Pro - Web Tải Nhạc & Video YouTube / Spotify

echo ========================================================
echo       Quốc Tín Media Pro - YouTube & Spotify Downloader
echo          Chất Lượng Âm Thanh Cao Nhất (320kbps)
echo ========================================================
echo.

set "PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if not exist "%PYTHON_PATH%" (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_PATH=python"
    ) else (
        echo [!] Không tìm thấy Python 3.12!
        pause
        exit /b 1
    )
)

echo [*] Đang khởi động máy chủ Web...
echo [*] Mở trên máy tính:   http://127.0.0.1:5500
echo [*] Mở trên điện thoại: http://192.168.50.130:5500 (cùng mạng Wi-Fi)
start http://127.0.0.1:5500
"%PYTHON_PATH%" app.py

pause
