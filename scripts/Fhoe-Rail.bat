@echo off
setlocal

chcp 65001

cd .\3rdparty\Fhoe-Rail
if %errorlevel% neq 0 (
    echo "错误：请先安装锄大地功能后再使用！"
    echo "你可以从QQ群855392201的群文件中获取锄大地补丁包"
    exit /b %errorlevel%
)

echo 安装依赖...
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt requests
if %errorlevel% neq 0 (
    exit /b %errorlevel%
)

echo 启动任务...
python Fast_Star_Rail.py
if %errorlevel% neq 0 (
    exit /b %errorlevel%
)

endlocal
