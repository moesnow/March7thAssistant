<div align="center">
  <h1 align="center">
    <img src="./assets/screenshot/March7th.png" width="200">
    <br/>
    March7thAssistant
  </h1>
  <a href="https://trendshift.io/repositories/3892" target="_blank"><img src="https://trendshift.io/api/badge/repositories/3892" alt="moesnow%2FMarch7thAssistant | Trendshift" style="width: 200px; height: 46px;" width="250" height="46"/></a>
</div>

<br/>

<div align="center">
🌟 點一下右上角的 Star，Github 主頁就能收到軟件更新通知了哦~
</div>

<div align="center">
    <img src="assets/screenshot/star.gif" alt="Star" width="186" height="60">
  </a>
</div>

<br/>

<div align="center">

[简体中文](./README.md) | **繁體中文** | [English](./README_EN.md) | [日本語](./README_JA.md)

**繁體中文版本由 ChatGPT 生成，遊戲內語言目前僅支援簡體中文**

快速上手，請訪問：[使用教程](https://m7a.top/#/assets/docs/Tutorial)

遇到問題，請在提問前查看：[FAQ](https://m7a.top/#/assets/docs/FAQ)

</div>

## 功能簡介

- **日常**：清體力、每日實訓、領取獎勵、委託、鋤大地
- **周常**：歷戰餘響、貨幣戰爭、模擬宇宙、忘卻之庭
- **抽卡記錄導出**：支持 [UIGF](https://uigf.org/zh/standards/uigf.html)/[SRGF](https://uigf.org/zh/standards/srgf.html) 標準、**自動對話**
- 每日實訓等任務的完成情況支持**消息推送**
- 任務刷新或體力恢復到指定值後**自動啟動**
- 任務完成後**聲音提示、遊戲自動關閉或關機等**

> 其中模擬宇宙調用的 [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) 項目，鋤大地調用的 [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 項目

詳情見 [配置文件](assets/config/config.example.yaml) 或圖形界面設置 ｜QQ群 [點擊跳轉](https://qm.qq.com/q/C3IryUWCQw) TG群 [點擊跳轉](https://t.me/+ZgH5zpvFS8o0NGI1)

## 界面展示

![README](assets/screenshot/README.png)

## 注意事項

- 必須使用**PC端** `1920*1080` 分辨率窗口或全屏運行遊戲（不支援HDR）
- 支援 **macOS** 和 **Linux**（僅陸服雲遊戲模式），也支援 [Docker 部署](https://m7a.top/#/assets/docs/Docker)
- 模擬宇宙相關 [項目文檔](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md)  [Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)
- 需要後台運行或多顯示器可以嘗試 [遠程本地多用戶桌面](https://asu.stysqy.top/guide/bs.html)
- 遇到錯誤請在 [Issue](https://github.com/moesnow/March7thAssistant/issues) 反饋，提問討論可以在 [Discussions](https://github.com/moesnow/March7thAssistant/discussions) ，群聊隨緣看。

- 歡迎通過 [PR](https://github.com/moesnow/March7thAssistant/pulls) 貢獻，提交前請先閱讀 [貢獻指南](CONTRIBUTING.md)

## 下載安裝

前往 [Releases](https://github.com/moesnow/March7thAssistant/releases/latest) 下載後解壓雙擊三月七圖標的 `March7th Launcher.exe` 打開圖形界面

如果需要使用 **任務計劃程序** 定時運行或直接執行 **完整運行**，可以使用終端圖標的 `March7th Assistant.exe`

檢測更新可以點擊圖形界面設置最底下的按鈕，或雙擊 `March7th Updater.exe`

### 命令列參數

圖形界面 `March7th Launcher.exe` 支援命令列參數，啟動時即可自動執行指定任務：

```bash
# 查看說明
March7th Launcher.exe -h

# 列出所有可用任務
March7th Launcher.exe -l

# 啟動圖形界面並執行完整運行
March7th Launcher.exe main

# 啟動圖形界面並執行每日實訓
March7th Launcher.exe daily

# 任務正常完成後自動退出（需配合任務參數）
March7th Launcher.exe main -e
```

<details>
<summary>可用任務列表</summary>

| 任務名稱 | 說明 |
|---------|------|
| main | 完整運行 |
| daily | 每日實訓 |
| power | 清體力 |
| currencywars | 貨幣戰爭 |
| currencywarsloop | 貨幣戰爭循環 |
| fight | 鋤大地 |
| universe | 模擬宇宙 |
| forgottenhall | 混沌回憶 |
| purefiction | 虛構敘事 |
| apocalyptic | 末日幻影 |
| redemption | 兌換碼 |
| universe_gui | 模擬宇宙原生界面 |
| fight_gui | 鋤大地原生界面 |
| universe_update | 模擬宇宙更新 |
| fight_update | 鋤大地更新 |
| game | 啟動遊戲 |
| notify | 測試消息推送 |

</details>

## 源碼運行

如果你是完全不懂的小白，請通過上面的方式下載安裝，不用往下看了。

推薦使用 Python 3.12 或更高版本。
```cmd
# Installation (using venv is recommended)
git clone --recurse-submodules https://github.com/moesnow/March7thAssistant
cd March7thAssistant
pip install -r requirements.txt
python app.py
python main.py

# Update
git pull
git submodule update --init --recursive
```

如果使用 `uv`，建議直接使用專案內建的 `pyproject.toml` 工作流：

```cmd
# Installation (using uv)
git clone --recurse-submodules https://github.com/moesnow/March7thAssistant
cd March7thAssistant
uv sync

# 啟動圖形界面
uv run python app.py

# 查看命令列說明
uv run python main.py -h

# 執行完整運行
uv run python main.py

# 執行每日實訓
uv run python main.py daily
```

<details>
<summary>開發相關</summary>

獲取 crop 參數表示的裁剪坐標可以通過圖形界面設置內的捕獲截圖功能

python main.py 後面支持參數 fight/universe/forgottenhall 等

</details>

---

如果喜歡本項目，可以微信贊贊送作者一杯咖啡☕

您的支持就是作者開發和維護項目的動力🚀

![sponsor](assets/app/images/sponsor.jpg)

---

## 相關項目

March7thAssistant 離不開以下開源項目的幫助：

- 模擬宇宙自動化 [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe)

- 鋤大地自動化 [https://github.com/linruowuyin/Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail)

- OCR文字識別 [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)

- 圖形界面組件庫 [https://github.com/zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)


## Contributors
<a href="https://github.com/moesnow/March7thAssistant/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=moesnow/March7thAssistant" />

</a>

## Stargazers over time

[![Star History](https://starchart.cc/moesnow/March7thAssistant.svg?variant=adaptive)](https://starchart.cc/moesnow/March7thAssistant)
