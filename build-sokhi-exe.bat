@echo off
title Sokhi App Build
echo ================================================
echo   Sokhi App (Sokhi.exe) is being built...
echo   First time may take a few minutes. Please wait.
echo ================================================
cd /d %~dp0
where python >nul 2>nul
if errorlevel 1 goto NO_PYTHON
if not exist sokhi.py goto NO_SOKHI
if not exist sokhi_app.py goto NO_LAUNCHER
echo.
echo Step 1 of 3: Installing free tools (PyInstaller, pywebview, pystray, segno, edge-tts)...
python -m pip install --upgrade --disable-pip-version-check pyinstaller pywebview pystray pillow segno edge-tts > build-log.txt 2>&1
if errorlevel 1 goto PIP_FAIL
echo.
echo Step 2 of 3: Building Sokhi.exe...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Sokhi --icon sokhi.ico --collect-all webview --hidden-import edge_tts --hidden-import edge_tts.__main__ --hidden-import segno --hidden-import pystray._win32 sokhi_app.py >> build-log.txt 2>&1
if errorlevel 1 goto BUILD_FAIL
copy /y dist\Sokhi.exe .\Sokhi.exe >nul
if not exist Sokhi.exe goto COPY_FAIL
rmdir /s /q build >nul 2>nul
rmdir /s /q dist >nul 2>nul
del /q Sokhi.spec >nul 2>nul
echo.
echo Step 3 of 3: Creating Desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $lnk=$ws.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'Sokhi.lnk')); $lnk.TargetPath='%CD%\Sokhi.exe'; $lnk.WorkingDirectory='%CD%'; if (Test-Path '%CD%\sokhi.ico') { $lnk.IconLocation='%CD%\sokhi.ico,0' }; $lnk.Description='Sokhi'; $lnk.Save()"
echo.
echo ================================================
echo   DONE! Sokhi.exe is ready.
echo.
echo   Now double-click the Sokhi icon on your Desktop.
echo   Sokhi will open in its own window - no browser needed.
echo   Your PIN is in this folder: data\pin.txt
echo ================================================
goto END
:NO_PYTHON
echo.
echo [PROBLEM] Python not found on this PC!
echo Install free Python: https://www.python.org/downloads/
echo IMPORTANT: during install, tick 'Add python.exe to PATH'.
goto END
:NO_SOKHI
echo.
echo [PROBLEM] sokhi.py is not in this folder!
echo Put all app-pack files into the real Sokhi folder
echo (the one that has sokhi.py and the data folder), then run again.
goto END
:NO_LAUNCHER
echo.
echo [PROBLEM] sokhi_app.py is missing in this folder!
echo Make sure all files from the app pack are in this folder.
goto END
:PIP_FAIL
echo.
echo [PROBLEM] Could not install the tools.
echo Check your internet connection, then run this file again.
echo Details are saved in build-log.txt - send a photo of it to Saba.
goto END
:BUILD_FAIL
echo.
echo [PROBLEM] Could not build Sokhi.exe.
echo Details are saved in build-log.txt - send a photo of it to Saba.
goto END
:COPY_FAIL
echo.
echo [PROBLEM] Sokhi.exe could not be copied.
echo If Sokhi is running, close it first, then run this file again.
goto END
:END
echo.
pause
