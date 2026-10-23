@echo off
chcp 65001 >nul
title Sokhi App তৈরি হচ্ছে
echo ================================================
echo   Sokhi App (Sokhi.exe) তৈরি হচ্ছে...
echo   প্রথমবার কয়েক মিনিট লাগতে পারে, অপেক্ষা করো।
echo ================================================
where python >nul 2>nul
if %errorlevel% neq 0 (
  echo.
  echo [সমস্যা] Python পাওয়া যায়নি!
  echo ফ্রি Python বসাও: https://www.python.org/downloads/
  echo বসানোর সময় নিচে "Add python.exe to PATH" টিক দিতে ভুলবে না।
  pause
  exit /b 1
)
cd /d %~dp0
if not exist sokhi.py (
  echo.
  echo [সমস্যা] এই ফোল্ডারে sokhi.py নেই!
  echo app-pack-এর ফাইলগুলো Sokhi-র আসল ফোল্ডারে রাখো — যেখানে
  echo sokhi.py আর data ফোল্ডার আছে — তারপর আবার চালাও।
  pause
  exit /b 1
)
if not exist sokhi_app.py (
  echo.
  echo [সমস্যা] sokhi_app.py পাওয়া যাচ্ছে না!
  echo pack-এর সব ফাইল এই ফোল্ডারে আছে কিনা দেখো।
  pause
  exit /b 1
)
echo.
echo ধাপ ১/৩: দরকারি ফ্রি টুল বসছে (PyInstaller, pywebview, pystray, segno, edge-tts)...
python -m pip install --upgrade --disable-pip-version-check pyinstaller pywebview pystray pillow segno edge-tts
if %errorlevel% neq 0 (
  echo.
  echo [সমস্যা] টুল বসাতে পারলাম না — ইন্টারনেট সংযোগ ঠিক আছে কিনা
  echo দেখে আবার build-sokhi-exe.bat চালাও।
  pause
  exit /b 1
)
echo.
echo ধাপ ২/৩: Sokhi.exe বানানো হচ্ছে...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Sokhi --icon sokhi.ico --collect-all webview --hidden-import edge_tts --hidden-import edge_tts.__main__ --hidden-import segno --hidden-import pystray._win32 sokhi_app.py
if %errorlevel% neq 0 (
  echo.
  echo [সমস্যা] Sokhi.exe বানাতে পারলাম না।
  echo ওপরের লেখাগুলোর একটা ছবি তুলে Saba-কে পাঠাও।
  pause
  exit /b 1
)
copy /y dist\Sokhi.exe .\Sokhi.exe >nul
if not exist Sokhi.exe (
  echo.
  echo [সমস্যা] Sokhi.exe কপি হয়নি — Sokhi চালু থাকলে আগে বন্ধ করে আবার চালাও।
  pause
  exit /b 1
)
rmdir /s /q build >nul 2>nul
rmdir /s /q dist >nul 2>nul
del /q Sokhi.spec >nul 2>nul
echo.
echo ধাপ ৩/৩: Desktop-এ Sokhi-র shortcut বানানো হচ্ছে...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $lnk=$ws.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'Sokhi.lnk')); $lnk.TargetPath='%CD%\Sokhi.exe'; $lnk.WorkingDirectory='%CD%'; if (Test-Path '%CD%\sokhi.ico') { $lnk.IconLocation='%CD%\sokhi.ico,0' }; $lnk.Description='Sokhi'; $lnk.Save()"
echo.
echo ================================================
echo   হয়ে গেছে! Sokhi.exe তৈরি।
echo.
echo   এখন Desktop-এর "Sokhi" আইকনে ডাবল-ক্লিক করলেই
echo   Sokhi তার নিজের উইন্ডোতে খুলবে — browser লাগবে না।
echo   PIN আছে এই ফোল্ডারের data\pin.txt ফাইলে।
echo ================================================
pause
