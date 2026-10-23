@echo off
chcp 65001 >nul
title Sokhi Desktop — Super Sokhi
echo ================================================
echo   Sokhi চালু হচ্ছে, ভাইয়া...
echo ================================================
where python >nul 2>nul
if %errorlevel% neq 0 (
  echo Python পাওয়া যায়নি!
  echo ফ্রি Python বসাও: https://www.python.org/downloads/
  echo বসানোর সময় নিচে "Add python.exe to PATH" টিক দিতে ভুলবে না।
  pause
  exit /b
)
cd /d %~dp0
python -c "import edge_tts" >nul 2>nul || if exist data\edge-tts.done del data\edge-tts.done
if not exist data\edge-tts.done (
  echo ভালো গলার জন্য ছোট্ট একটা ফ্রি টুল বসছে পেছনে... (শুধু প্রথমবার)
  start /min cmd /c "python -m pip install --quiet edge-tts && echo done> data\edge-tts.done"
)
python -c "import segno" >nul 2>nul || if exist data\segno.done del data\segno.done
if not exist data\segno.done (
  echo QR কোডের জন্য ছোট্ট একটা ফ্রি টুল বসছে পেছনে... (শুধু প্রথমবার)
  start /min cmd /c "python -m pip install --quiet segno && echo done> data\segno.done"
)
python -u sokhi.py
pause
