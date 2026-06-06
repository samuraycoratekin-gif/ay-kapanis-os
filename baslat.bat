@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Ay Kapanis OS baslatiliyor...

echo Eski sunucu (port 5050) kontrol ediliyor...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5050" ^| findstr "LISTENING"') do (
    echo   Eski surec kapatiliyor: PID %%a
    taskkill /f /pid %%a >nul 2>&1
)

set GIRIS_PAROLASI=1234
echo.
echo ================================================
echo   Varsayilan giris e-posta : ofis@aykapanis.local
echo   Varsayilan giris parola  : 1234
echo   Giris adresi             : http://localhost:5050/giris
echo ================================================
echo.
python app.py
pause
