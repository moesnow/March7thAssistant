<div align="center">
<p>
    <img src="./assets/screenshot/March7th.png">
</p>

<h1>
三月七小助手<br>
March7thAssistant
</h1>

<p>
    <img alt="" src="https://img.shields.io/badge/platform-Windows-blue?style=flat-square&color=4096d8" />
    <img alt="" src="https://img.shields.io/github/last-commit/moesnow/March7thAssistant?style=flat-square&color=f18cb9" />
    <img alt="" src="https://img.shields.io/github/v/release/moesnow/March7thAssistant?style=flat-square&color=4096d8" />
    <img alt="" src="https://img.shields.io/github/downloads/moesnow/March7thAssistant/total?style=flat-square&color=f18cb9" />
</p>

[简体中文](./README.md) | **繁體中文** | [English](./README_EN.md)

**繁體中文版本由 ChatGPT 生成，遊戲內語言目前僅支援簡體中文**

快速上手，請訪問：[使用教程](https://moesnow.github.io/March7thAssistant/#/assets/docs/Tutorial)

遇到問題，請在提問前查看：[FAQ](https://moesnow.github.io/March7thAssistant/#/assets/docs/FAQ)

</div>

## 功能簡介

- **日常**：清體力、每日實訓、領獎勵、委託、鋤大地
- **周常**：歷戰餘響、模擬宇宙、忘卻之庭
- 每日實訓等任務的完成情況支持消息推送
- 凌晨四點或體力恢復到指定值後自動啟動
- 任務完成後聲音提示、自動關閉遊戲或關機

> 其中模擬宇宙調用的 [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) 項目，鋤大地調用的 [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 項目

詳情見 [配置文件](assets/config/config.example.yaml) 或圖形界面設置 ｜🌟喜歡就給個星星吧|･ω･) 🌟｜QQ群 [855392201](https://qm.qq.com/q/9gFqUrUGVq) TG群 [點擊跳轉](https://t.me/+ZgH5zpvFS8o0NGI1)

## 界面展示

![README](assets/screenshot/README1.png)

## 注意事項

- 必須使用**PC端** `1920*1080` 分辨率窗口或全屏運行遊戲（不支援HDR）
- 模擬宇宙相關 [項目文檔](https://asu.stysqy.top/)  [Q&A](https://asu.stysqy.top/guide/qa.html)
- 需要後台運行或多顯示器可以嘗試 [遠程本地多用戶桌面](https://asu.stysqy.top/guide/bs.html)
- 遇到錯誤請在 [Issue](https://github.com/moesnow/March7thAssistant/issues) 反饋，提問討論可以在 [Discussions](https://github.com/moesnow/March7thAssistant/discussions) ，群聊隨緣看，歡迎 [PR](https://github.com/moesnow/March7thAssistant/pulls)

## 下載安裝

前往 [Releases](https://github.com/moesnow/March7thAssistant/releases/latest) 下載後解壓雙擊三月七圖標的 `March7th Launcher.exe` 打開圖形界面

如果需要使用 **任務計劃程序** 定時運行或直接執行 **完整運行**，可以使用終端圖標的 `March7th Assistant.exe`

檢測更新可以點擊圖形界面設置最底下的按鈕，或雙擊 `Update.exe`

## 源碼運行

如果你是完全不懂的小白，請通過上面的方式下載安裝，不用往下看了。

```cmd
git clone https://github.com/moesnow/March7thAssistant
cd March7thAssistant
pip install -r requirements.txt
python app.py
python main.py
```

<details>
<summary>開發相關</summary>

獲取 crop 參數表示的裁剪坐標可以通過圖形界面設置內的捕獲截圖功能

python main.py 後面支持參數 fight/universe/forgottenhall 等

</details>

---

如果喜歡本項目，可以微信贊贊送作者一杯咖啡☕

您的支持就是作者開發和維護項目的動力🚀

![sponsor](assets/screenshot/sponsor.jpg)

---

## 相關項目

March7thAssistant 離不開以下開源項目的幫助：

- 模擬宇宙自動化 [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe)

- 鋤大地自動化 [https://github.com/linruowuyin/Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail)

- OCR文字識別 [https://github.com/hiroi-sora/PaddleOCR-json](https://github.com/hiroi-sora/PaddleOCR-json)

- 圖形界面組件庫 [https://github.com/zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)


## Contributors
<a href="https://github.com/moesnow/March7thAssistant/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=moesnow/March7thAssistant" />

</a>

## Stargazers over time

[![Star History](https://starchart.cc/moesnow/March7thAssistant.svg)](https://starchart.cc/moesnow/March7thAssistant)