@echo off
setlocal

chcp 65001

echo 关闭 March7thAssistant 后按任意键继续
pause

echo 下载地址：%1

echo 下载中...
powershell -Command "(New-Object System.Net.WebClient).DownloadFile('%1', '.\March7thAssistant.zip')"
echo 下载完成

echo 开始解压...
powershell -Command "Expand-Archive -Path '.\March7thAssistant.zip' -DestinationPath './' -Force"
echo 解压完成

echo 开始更新...
xcopy "%2\*" ".\" /s /i /y
echo 删除文件...
rmdir /s /q "%2"
del March7thAssistant.zip
echo 更新完成

endlocal
