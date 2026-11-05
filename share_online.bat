@echo off
chcp 65001 > nul
title Chia Sẻ Quốc Tín Media Pro Lên Internet (Cloudflare Tunnel)

echo ========================================================
echo   Quốc Tín Media Pro - Chia Sẻ Ra Mạng Internet
echo ========================================================
echo.
echo [*] Đang thiết lập đường hầm bảo mật HTTPS...
echo [*] Vui lòng tìm dòng link có đuôi: .trycloudflare.com bên dưới:
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

