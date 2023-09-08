@echo off
setlocal

chcp 65001

cd .\3rdparty\Auto_Simulated_Universe
if %errorlevel% neq 0 (
    exit /b %errorlevel%
)

echo 安装依赖...
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
if %errorlevel% neq 0 (
    exit /b %errorlevel%
)

echo 启动任务...
python align_angle.py
if %errorlevel% neq 0 (
    exit /b %errorlevel%
)

python states.py %*
if %errorlevel% neq 0 (
    exit /b %errorlevel%
)

endlocal
