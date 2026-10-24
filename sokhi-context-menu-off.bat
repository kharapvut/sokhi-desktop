@echo off
chcp 65001 >nul
title Sokhi - Right-click menu OFF
echo ================================================
echo   Sokhi right-click menu is being removed
echo ================================================
echo.
reg delete "HKCU\Software\Classes\*\shell\SokhiExplain" /f
if errorlevel 1 goto FAIL
echo.
echo DONE! The Sokhi menu was removed from right-click.
echo To add it again, run sokhi-context-menu-on.bat.
goto END
:FAIL
echo.
echo The menu was probably already removed.
goto END
:END
echo.
pause
