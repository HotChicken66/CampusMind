@echo off
chcp 65001 >nul
color 0B

echo ========================================================
echo     [QQ Bot] All-in-One Launcher (v3.2 - Dual-Lang Fix)
echo ========================================================
echo.
echo Launching services... 

:: Config
set "PY_EXE=D:\condaData\envs_dirs\QQbot\python.exe"
set "PROJECT_ROOT=d:\Python\QQbot"

:: Process 1: NapCat Protocol 
echo [1/4] Starting NapCat Protocol...
start "QQ Bot - Protocol (NapCat)" cmd /c "cd /d "%PROJECT_ROOT%\NapCat\NapCat.44498.Shell" && napcat.bat"

:: Delay for 3 seconds to let NapCat claim the port
timeout /t 3 /nobreak >nul

:: Process 2: ASGI FastAPI Web Admin
echo [2/4] Starting Web Admin Dashboard (8080)...
start "QQ Bot - Web Admin (8080)" cmd /k "cd /d "%PROJECT_ROOT%" && "%PY_EXE%" scripts\weekly_admin_service.py"

:: Process 3: Evaluation & Tagging Dashboard
echo [3/4] Starting Evaluation Dashboard (8081)...
start "QQ Bot - Eval Dashboard (8081)" cmd /k "cd /d "%PROJECT_ROOT%" && "%PY_EXE%" eval\ui_server.py"

:: Process 4: NoneBot Core
echo [4/4] Starting NoneBot Core Engine...
start "QQ Bot - Core (NoneBot)" cmd /k "cd /d "%PROJECT_ROOT%" && "%PY_EXE%" bot.py"

echo.
echo ========================================================
echo Deployment Complete! 4 separate terminals launched.
echo.
echo Dashboard URLs:
echo - Admin: http://127.0.0.1:8080
echo - Eval:  http://127.0.0.1:8081
echo.
echo To shut down, close those 4 terminal windows manually.
echo ========================================================
timeout /t 5 >nul
exit