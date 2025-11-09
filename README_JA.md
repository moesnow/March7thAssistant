<div align="center">
  <h1 align="center">
    <img src="./assets/screenshot/March7th.png" width="200">
    <br/>
    March7thAssistant · 三月七小助手
  </h1>
  <a href="https://trendshift.io/repositories/3892" target="_blank"><img src="https://trendshift.io/api/badge/repositories/3892" alt="moesnow%2FMarch7thAssistant | Trendshift" style="width: 200px; height: 46px;" width="250" height="46"/></a>
</div>

<br/>

<div align="center">
  <img alt="" src="https://img.shields.io/badge/platform-Windows-blue?style=flat-square&color=4096d8" />
  <img alt="" src="https://img.shields.io/github/v/release/moesnow/March7thAssistant?style=flat-square&color=f18cb9" />
  <img alt="" src="https://img.shields.io/github/downloads/moesnow/March7thAssistant/total?style=flat-square&color=4096d8" />
</div>

<br/>

<div align="center">

[简体中文](./README.md) | [繁體中文](./README_TW.md) | [English](./README_EN.md) | **日本語**

クイックスタートガイド：[使用チュートリアル](https://m7a.top/#/assets/docs/Tutorial)

問題が発生した場合は、質問する前にこちらをご確認ください：[FAQ](https://m7a.top/#/assets/docs/FAQ)

</div>

## 機能紹介

- **日常タスク**：開拓力消化、デイリー訓練、報酬受取、委託、フィールド探索
- **週次タスク**：歴戦余韻、模擬宇宙、忘却の庭
- **ガチャ記録エクスポート**：[SRGF](https://uigf.org/zh/standards/SRGF.html) 標準対応、**自動会話**
- デイリー訓練などのタスク完了状況を**メッセージ通知**
- タスク更新時や開拓力が指定値まで回復した際に**自動起動**
- タスク完了後に**音声通知、ゲーム自動終了、シャットダウンなど**

> 模擬宇宙は [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) プロジェクトを、フィールド探索は [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) プロジェクトを使用しています

詳細は [設定ファイル](assets/config/config.example.yaml) またはGUI設定をご覧ください ｜🌟気に入ったらスターをお願いします|･ω･) 🌟｜QQ群 [リンク](https://qm.qq.com/q/C3IryUWCQw) TG群 [リンク](https://t.me/+ZgH5zpvFS8o0NGI1)

## インターフェース

![README](assets/screenshot/README.png)

## 注意事項

- **PC版**で `1920*1080` 解像度のウィンドウまたはフルスクリーンでゲームを実行する必要があります（HDRには非対応）
- 模擬宇宙関連 [プロジェクトドキュメント](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md)  [Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)
- バックグラウンド実行やマルチディスプレイの場合は [リモートローカルマルチユーザーデスクトップ](https://m7a.top/#/assets/docs/Background) をお試しください
- エラーが発生した場合は [Issue](https://github.com/moesnow/March7thAssistant/issues) でフィードバックをお願いします。質問や議論は [Discussions](https://github.com/moesnow/March7thAssistant/discussions) へどうぞ。[PR](https://github.com/moesnow/March7thAssistant/pulls) も歓迎します

## ダウンロードとインストール

[Releases](https://github.com/moesnow/March7thAssistant/releases/latest) から最新版をダウンロードし、解凍後に三月七のアイコンの `March7th Launcher.exe` をダブルクリックしてGUIを開きます

**タスクスケジューラ**で定期実行したり、直接**完全実行**を行いたい場合は、ターミナルアイコンの `March7th Assistant.exe` を使用できます

更新確認は、GUI設定の最下部にあるボタンをクリックするか、`March7th Updater.exe` をダブルクリックしてください

## ソースコードから実行

初心者の方は、上記の方法でダウンロードとインストールを行ってください。以下の手順は不要です。

```cmd
# インストール (venv の使用を推奨)
git clone --recurse-submodules https://github.com/moesnow/March7thAssistant
cd March7thAssistant
pip install -r requirements.txt
python app.py
python main.py

# 更新
git pull
git submodule update --init --recursive
```

<details>
<summary>開発関連</summary>

crop パラメータで表されるトリミング座標を取得するには、アシスタントツールボックス内のスクリーンキャプチャ機能を使用できます

python main.py の後に fight/universe/forgottenhall などのパラメータを指定できます

</details>

---

このプロジェクトを気に入っていただけた場合、WeChat で作者にコーヒー代を寄付できます☕

あなたのサポートが作者の開発とプロジェクト維持のモチベーションです🚀

![sponsor](assets/app/images/sponsor.jpg)

---

## 関連プロジェクト

March7thAssistant は以下のオープンソースプロジェクトのサポートを受けています：

- 模擬宇宙自動化 [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe)

- フィールド探索自動化 [https://github.com/linruowuyin/Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail)

- OCR文字認識 [https://github.com/hiroi-sora/PaddleOCR-json](https://github.com/hiroi-sora/PaddleOCR-json)

- GUIコンポーネントライブラリ [https://github.com/zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)


## Contributors
<a href="https://github.com/moesnow/March7thAssistant/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=moesnow/March7thAssistant" />

</a>

## Stargazers over time

[![Star History](https://starchart.cc/moesnow/March7thAssistant.svg?variant=adaptive)](https://starchart.cc/moesnow/March7thAssistant)
