@echo off
setlocal

chcp 65001

cd .\3rdparty

echo 下载中...
powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://ghproxy.com/https://github.com/CHNZYX/Auto_Simulated_Universe/archive/main.zip', '.\Auto_Simulated_Universe.zip')"
echo 下载完成

echo 开始解压...
powershell -Command "Expand-Archive -Path '.\Auto_Simulated_Universe.zip' -DestinationPath './' -Force"
echo 解压完成

echo 开始更新...
echo 删除文件...
rmdir /s /q "Auto_Simulated_Universe"
del Auto_Simulated_Universe.zip
echo 重命名文件夹...
ren Auto_Simulated_Universe-main Auto_Simulated_Universe
echo 更新完成

endlocal
