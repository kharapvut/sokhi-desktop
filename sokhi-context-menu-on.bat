@echo off
chcp 65001 >nul
title Sokhi — ডান-ক্লিক মেনু চালু করা
echo ================================================
echo   Sokhi — ডান-ক্লিক মেনু চালু করা হচ্ছে
echo ================================================
echo.
if not exist "%~dp0Sokhi.exe" (
  echo সতর্কতা: এই ফোল্ডারে Sokhi.exe পাওয়া যায়নি!
  echo এই .bat ফাইলটা Sokhi.exe-র পাশের ফোল্ডারেই রাখতে হবে।
  echo মেনু যোগ করা হলো না।
  echo.
  pause
  exit /b 1
)
reg add "HKCU\Software\Classes\*\shell\SokhiExplain" /ve /d "Sokhi দিয়ে বুঝাও" /f
if errorlevel 1 (
  echo দুঃখিত — মেনু যোগ করা যায়নি।
  pause
  exit /b 1
)
reg add "HKCU\Software\Classes\*\shell\SokhiExplain" /v Icon /d "%~dp0sokhi.ico" /f >nul
reg add "HKCU\Software\Classes\*\shell\SokhiExplain\command" /ve /d "\"%~dp0Sokhi.exe\" --explain \"%%1\"" /f >nul
echo.
echo হয়ে গেছে! এখন থেকে যেকোনো ফাইলে ডান-ক্লিক করলেই
echo "Sokhi দিয়ে বুঝাও" মেনুটা দেখতে পাবে।
echo ফাইলে ক্লিক করলে Sokhi সেটা সহজ বাংলায় বুঝিয়ে দেবে।
echo.
echo মেনু সরাতে চাইলে sokhi-context-menu-off.bat চালাও।
echo.
pause
