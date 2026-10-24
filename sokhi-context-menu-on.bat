@echo off
chcp 65001 >nul
title Sokhi - Right-click menu ON
echo ================================================
echo   Sokhi right-click menu is being added
echo ================================================
echo.
if exist "%~dp0Sokhi.exe" goto HAVE_EXE
echo WARNING: Sokhi.exe not found in this folder!
echo Keep this bat file in the same folder as Sokhi.exe.
echo The menu was NOT added.
goto END
:HAVE_EXE
reg add "HKCU\Software\Classes\*\shell\SokhiExplain" /ve /d "Sokhi দিয়ে বুঝাও" /f
if errorlevel 1 goto FAIL
reg add "HKCU\Software\Classes\*\shell\SokhiExplain" /v Icon /d "%~dp0sokhi.ico" /f >nul
reg add "HKCU\Software\Classes\*\shell\SokhiExplain\command" /ve /d "\"%~dp0Sokhi.exe\" --explain \"%%1\"" /f >nul
echo.
echo DONE! Now right-click any file and you will see
echo the "Sokhi diye bujhao" menu. Sokhi will explain
echo the file in simple Bangla.
echo.
echo To remove the menu, run sokhi-context-menu-off.bat.
goto END
:FAIL
echo Sorry - the menu could not be added.
goto END
:END
echo.
pause
