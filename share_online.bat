@echo off
chcp 65001 > nul
title Chia Se Quoc Tin Media Pro Len Internet (Cloudflare Tunnel)

echo ========================================================
echo   Quoc Tin Media Pro - Chia Se Ra Mang Internet
echo ========================================================
echo.
echo [*] Dang thiet lap duong ham bao mat HTTPS...
echo [*] Vui long tim dong link co duoi: .trycloudflare.com ben duoi:
echo.

set "CF_EXE=C:\Program Files (x86)\cloudflared\cloudflared.exe"
if not exist "%CF_EXE%" (
    set "CF_EXE=C:\Program Files\cloudflared\cloudflared.exe"
)
if not exist "%CF_EXE%" (
    set "CF_EXE=cloudflared"
)

"%CF_EXE%" tunnel --url http://127.0.0.1:5500

pause
