@echo off
chcp 65001 > nul
title Chia S? Web V?i T?n Mi?n T? Ch?n (Localtunnel)

echo ========================================================
echo   Qu?c T?n Media Pro - T? ??t T?n Mi?n Mi?n Ph?
echo ========================================================
echo.
set "DEFAULT_NAME=quoctinmedia"
set /p SUBDOMAIN="Nh?p t?n mi?n b?n mu?n (nh?n Enter ?? d?ng '%DEFAULT_NAME%'): "
if "%SUBDOMAIN%"=="" set "SUBDOMAIN=%DEFAULT_NAME%"

echo.
echo [*] ?ang thi?t l?p ???ng d?n c? ??nh...
echo [*] Link trang web c?a b?n s? l?: https://%SUBDOMAIN%.loca.lt
echo.

npx.cmd localtunnel --port 5500 --subdomain %SUBDOMAIN%

pause

