@echo off
title Push Code to GitHub - Quoc Tin Media Pro

echo ========================================================
echo   Quoc Tin Media Pro - Push Code to GitHub
echo ========================================================
echo.
echo [*] Dang day code len GitHub...
echo.

git push -u origin main --force

echo.
echo ========================================================
echo [OK] Da day code len GitHub thanh cong!
echo Bay gio hay quay lai Render va bam:
echo "Manual Deploy" -^> "Clear build cache & deploy"
echo ========================================================
pause
