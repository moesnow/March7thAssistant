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
🌟 右上のスターをクリックすると、GitHub のホームページでソフトウェアの更新通知を受け取れますよ~
</div>

<div align="center">
    <img src="assets/screenshot/star.gif" alt="Star" width="186" height="60">
  </a>
</div>

<br/>

<div align="center">

[简体中文](./README.md) | [繁體中文](./README_TW.md) | [English](./README_EN.md) | **日本語**

**ゲーム内の言語は現在、簡体字中国語のみに対応しています。**

クイックスタートガイド：[使用チュートリアル](https://m7a.top/#/assets/docs/Tutorial)

問題が発生した場合は、質問する前にこちらをご確認ください：[FAQ](https://m7a.top/#/assets/docs/FAQ)

</div>

## 機能紹介

- **日常タスク**：開拓力消化、デイリー訓練、報酬受取、委託、フィールド探索
- **週次タスク**：歴戦余韻、貨幣戦争、模擬宇宙、忘却の庭
- **ガチャ記録エクスポート**：[UIGF](https://uigf.org/zh/standards/uigf.html)/[SRGF](https://uigf.org/zh/standards/srgf.html) 標準対応、**自動会話**
- デイリー訓練などのタスク完了状況を**メッセージ通知**
- タスク更新時や開拓力が指定値まで回復した際に**自動起動**
- タスク完了後に**音声通知、ゲーム自動終了、シャットダウンなど**

> 模擬宇宙は [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) プロジェクトを、フィールド探索は [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) プロジェクトを使用しています

詳細は [設定ファイル](assets/config/config.example.yaml) またはGUI設定をご覧ください ｜QQ群 [リンク](https://qm.qq.com/q/C3IryUWCQw) TG群 [リンク](https://t.me/+ZgH5zpvFS8o0NGI1)

## インターフェース

![README](assets/screenshot/README.png)

## 注意事項

- **PC版**で `1920*1080` 解像度のウィンドウまたはフルスクリーンでゲームを実行する必要があります（HDRには非対応）
- 模擬宇宙関連 [プロジェクトドキュメント](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md)  [Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)
- バックグラウンド実行やマルチディスプレイの場合は [リモートローカルマルチユーザーデスクトップ](https://m7a.top/#/assets/docs/Background) をお試しください
- エラーが発生した場合は [Issue](https://github.com/moesnow/March7thAssistant/issues) でフィードバックをお願いします。質問や議論は [Discussions](https://github.com/moesnow/March7thAssistant/discussions) へどうぞ。

- PR（プルリクエスト）は歓迎しますが、送る前に [CONTRIBUTING.md](CONTRIBUTING.md) をご確認ください。

## ダウンロードとインストール

[Releases](https://github.com/moesnow/March7thAssistant/releases/latest) から最新版をダウンロードし、解凍後に三月七のアイコンの `March7th Launcher.exe` をダブルクリックしてGUIを開きます

**タスクスケジューラ**で定期実行したり、直接**完全実行**を行いたい場合は、ターミナルアイコンの `March7th Assistant.exe` を使用できます

更新確認は、GUI設定の最下部にあるボタンをクリックするか、`March7th Updater.exe` をダブルクリックしてください

### コマンドライン引数

GUI の `March7th Launcher.exe` はコマンドライン引数に対応しており、起動時に指定したタスクを自動実行できます：

```bash
# ヘルプを表示
March7th Launcher.exe -h

# すべてのタスクを一覧表示
March7th Launcher.exe -l

# GUI を起動してフル実行
March7th Launcher.exe main

# GUI を起動してデイリー訓練を実行
March7th Launcher.exe daily

# タスク完了後に自動終了（TASK と併用）
March7th Launcher.exe main -e
```

<details>
<summary>利用可能なタスク一覧</summary>

| タスク | 説明 |
|-------|------|
| main | フル実行 |
| daily | デイリー訓練 |
| power | 開拓力消化 |
| currencywars | クレジット戦闘 |
| currencywarsloop | クレジット戦闘ループ |
| fight | フィールド探索 |
| universe | 模擬宇宙 |
| forgottenhall | 忘却の庭 |
| purefiction | 虚構叙事 |
| apocalyptic | 末日幻影 |
| redemption | 交換コード |
| universe_gui | 模擬宇宙（ネイティブUI） |
| fight_gui | フィールド探索（ネイティブUI） |
| universe_update | 模擬宇宙アップデート |
| fight_update | フィールド探索アップデート |
| game | ゲーム起動 |
| notify | 通知テスト |

</details>

## ソースコードから実行

初心者の方は、上記の方法でダウンロードとインストールを行ってください。以下の手順は不要です。

推奨 Python バージョンは 3.12 以上です。

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

- OCR文字認識 [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)

- GUIコンポーネントライブラリ [https://github.com/zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)


## Contributors
<a href="https://github.com/moesnow/March7thAssistant/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=moesnow/March7thAssistant" />

</a>

## Stargazers over time

[![Star History](https://starchart.cc/moesnow/March7thAssistant.svg?variant=adaptive)](https://starchart.cc/moesnow/March7thAssistant)
