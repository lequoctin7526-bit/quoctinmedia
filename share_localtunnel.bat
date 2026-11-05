@echo off
chcp 65001 > nul
title Chia Sẻ Web Với Tên Miền Tự Chọn (Localtunnel)

echo ========================================================
echo   Quốc Tín Media Pro - Tự Đặt Tên Miền Miễn Phí
echo ========================================================
echo.
set "DEFAULT_NAME=quoctinmedia"
set /p SUBDOMAIN="Nhập tên miền bạn muốn (nhấn Enter để dùng '%DEFAULT_NAME%'): "
if "%SUBDOMAIN%"=="" set "SUBDOMAIN=%DEFAULT_NAME%"

echo.
echo [*] Đang thiết lập đường dẫn cố định...
echo [*] Link trang web của bạn sẽ là: https://%SUBDOMAIN%.loca.lt
echo.

npx.cmd localtunnel --port 5500 --subdomain %SUBDOMAIN%

pause

