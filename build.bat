@echo off
rem Compile VLC Redesign en .exe (a lancer sous Windows, dans ce dossier)
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail
pyinstaller VLC_Redesign.spec --noconfirm --clean
if errorlevel 1 goto :fail
echo.
echo === Termine : dist\VLC Redesign\VLC Redesign.exe ===
where iscc >nul 2>nul
if %errorlevel%==0 (
  iscc installer.iss
  echo === Installateur : Output\VLC_Redesign_Setup.exe ===
) else (
  echo Inno Setup non trouve : installateur non genere ^(optionnel^).
)
pause
exit /b 0
:fail
echo Echec de la compilation.
pause
exit /b 1
