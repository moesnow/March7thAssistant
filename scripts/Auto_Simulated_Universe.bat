@echo off
setlocal

powershell -Command "$psVersionTable.PSEdition" >nul 2>&1
if %errorlevel% equ 0 (
    cd .\3rdparty\Auto_Simulated_Universe
) else (
    cd .\3rdparty\Auto_Simulated_Universe
)

echo Installing dependencies...
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

echo Starting application...
python align_angle.py
python states.py

endlocal
