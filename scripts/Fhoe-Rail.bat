@echo off
setlocal

cd .\3rdparty\Fhoe-Rail

echo Installing dependencies...
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt requests

echo Starting application...
python Fast_Star_Rail.py

endlocal
