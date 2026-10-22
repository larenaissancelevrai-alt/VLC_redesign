@echo off
cd /d "%~dp0"
echo === VLC Redesign ===
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Echec de l'installation des dependances.
  pause
  exit /b 1
)
python main.py
if errorlevel 1 pause
