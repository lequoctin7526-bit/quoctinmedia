# OmniMedia Pro Launcher for PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$PythonPath = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $PythonPath)) {
    $PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
}

if (-not $PythonPath) {
    Write-Host "[!] Không tìm thấy Python!" -ForegroundColor Red
    exit 1
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "      OmniMedia Pro - YouTube & Spotify Downloader" -ForegroundColor Green
Write-Host "         Chất Lượng Âm Thanh Cao Nhất (320kbps)" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

Start-Process "http://127.0.0.1:5000"
& $PythonPath app.py
