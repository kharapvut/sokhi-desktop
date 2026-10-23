@echo off
chcp 65001 >nul
title Sokhi — ডান-ক্লিক মেনু সরানো
echo ================================================
echo   Sokhi — ডান-ক্লিক মেনু সরানো হচ্ছে
echo ================================================
echo.
reg delete "HKCU\Software\Classes\*\shell\SokhiExplain" /f
if errorlevel 1 (
  echo.
  echo মেনুটা মনে হয় আগেই সরানো ছিল, অথবা সরানো যায়নি।
  echo.
  pause
  exit /b 1
)
echo.
echo হয়ে গেছে! ডান-ক্লিক মেনু থেকে "Sokhi দিয়ে বুঝাও" সরিয়ে দেওয়া হয়েছে।
echo আবার যোগ করতে চাইলে sokhi-context-menu-on.bat চালাও।
echo.
pause
