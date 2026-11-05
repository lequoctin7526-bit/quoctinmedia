@echo off
chcp 65001 > nul
title Đẩy Mã Nguồn Lên GitHub - Quốc Tín Media Pro

echo ========================================================
echo   Quốc Tín Media Pro - Đẩy Code Lên GitHub
echo ========================================================
echo.
echo [*] Đang đẩy code lên GitHub repository:
echo     https://github.com/lequoctin7526-bit/quoctinmedia
echo.
echo [*] Lưu ý: Nếu có cửa sổ nhỏ hoặc trình duyệt bật lên,
echo     bạn chỉ cần bấm "Sign in with your browser" để xác nhận.
echo.

git push -u origin main --force

echo.
echo ========================================================
echo [OK] Đã đẩy code lên GitHub thành công!
echo Hãy quay lại trang Render, bấm:
echo "Manual Deploy" -> "Deploy latest commit"
echo ========================================================
pause
