@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Ay Kapanis OS baslatiliyor...
python app.py
pause
