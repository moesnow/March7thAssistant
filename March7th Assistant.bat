@echo off
setlocal

powershell -Command "$psVersionTable.PSEdition" >nul 2>&1
if %errorlevel% equ 0 (
    cd %~dp0
) else (
    cd /d %~dp0
)

echo Installing dependencies...
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

echo Starting GUI application...
python app.py

pause
endlocal
