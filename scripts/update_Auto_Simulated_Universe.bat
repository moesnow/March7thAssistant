@echo off
setlocal

cd .\3rdparty\Auto_Simulated_Universe

echo Installing dependencies...
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

echo Starting application...
python update.py

endlocal
