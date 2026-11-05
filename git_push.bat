@echo off
chcp 65001 > nul
title Đẩy Mã Nguồn Lên GitHub - Quốc Tín Media Pro

echo ========================================================
echo   Quốc Tín Media Pro - Đẩy Code Lên GitHub Tự Động
echo ========================================================
echo.
echo Bước 1: Hãy tạo 1 Repository mới trên https://github.com/new
echo Bước 2: Copy link Repo (dạng https://github.com/username/repo.git)
echo.

set /p REPO_URL="Dán link GitHub Repository của bạn vào đây: "

if "%REPO_URL%"=="" (
    echo.
    echo [!] Bạn chưa nhập link. Vui lòng mở lại file và nhập link!
    pause
    exit /b 1
)

echo.
echo [*] Đang khởi tạo Git và lưu trữ file...
git init
git add .
git commit -m "Deploy Quoc Tin Media Pro"
git branch -M main
git remote remove origin >nul 2>nul
git remote add origin %REPO_URL%

echo [*] Đang đẩy code lên GitHub...
git push -u origin main --force

echo.
echo ========================================================
echo [OK] Đã đẩy code lên GitHub thành công!
echo Bây giờ bạn có thể vào https://render.com để kết nối Web Service.
echo ========================================================
pause

