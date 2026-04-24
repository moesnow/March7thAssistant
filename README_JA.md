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
🌟 右上の Star を押すと、GitHub で更新通知を受け取れます。
</div>

<div align="center">
    <img src="assets/screenshot/star.gif" alt="Star" width="186" height="60">
</div>

<br/>

<div align="center">

[简体中文](./README.md) | [繁體中文](./README_TW.md) | [English](./README_EN.md) | **日本語** | [한국어](./README_KR.md)

**このドキュメントは簡体字中国語版をもとに AI で翻訳しています。最終更新日: 2026-04-24。差異がある場合は簡体字中国語版を優先してください。**

**ゲーム内言語は現在、簡体字中国語のみ対応しています。**

クイックスタート: [使用チュートリアル](https://m7a.top/#/assets/docs/Tutorial_ja)

困ったときは先にこちらを確認してください: [FAQ](https://m7a.top/#/assets/docs/FAQ_ja)

</div>

## 機能紹介

- **日常**: 開拓力消化、デイリー訓練、報酬受け取り、委託、フィールド探索
- **週常**: 歴戦余韻、貨幣戦争、差分宇宙、混沌の記憶、虚構叙事、末日の幻影
- **雲・星穹鉄道**: バックグラウンド実行、ヘッドレス実行、Docker 実行に対応
- **ガチャ記録エクスポート**: [UIGF](https://uigf.org/zh/standards/uigf.html) / [SRGF](https://uigf.org/zh/standards/srgf.html) 標準に対応
- **ツールボックス**: 自動会話、FPS アンロック、交換コード
- デイリー訓練などの完了状況で **通知送信** に対応
- タスク更新時や開拓力が指定値まで回復したときの **自動起動** に対応
- タスク完了後の **音声通知、ゲーム自動終了、シャットダウンなど** に対応

詳細は GUI 設定または [設定ファイル](assets/config/config.example.yaml) を参照してください｜QQ 群 [リンク](https://qm.qq.com/q/C3IryUWCQw) TG 群 [リンク](https://t.me/+ZgH5zpvFS8o0NGI1) Bilibili [リンク](https://space.bilibili.com/3706960664857075)

## 画面イメージ

![README](assets/screenshot/README.png)

## 注意事項

- 不具合があれば [Issue](https://github.com/moesnow/March7thAssistant/issues) へ、質問や相談は [Discussions](https://github.com/moesnow/March7thAssistant/discussions) へどうぞ。チャットグループは常時確認していません。
- [PR](https://github.com/moesnow/March7thAssistant/pulls) は歓迎します。送る前に [貢献ガイド](CONTRIBUTING.md) を読んでください。

## ダウンロードとインストール

[Releases](https://github.com/moesnow/March7thAssistant/releases/latest) から最新版をダウンロードして解凍し、三月七アイコンの `March7th Launcher.exe` をダブルクリックして GUI を開きます。

## ソースから実行

完全な初心者であれば、上の配布版を使ってください。この先は見なくて構いません。

Python 3.12 以上を推奨します。

Windows でターミナルから起動する場合は、管理者権限で PowerShell、Windows Terminal、または CMD を開くことを推奨します。Windows 11 24H2 以降であれば [Sudo for Windows](https://learn.microsoft.com/zh-cn/windows/advanced-settings/sudo/) も利用できます。

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

`uv` を使う場合は、プロジェクト付属の `pyproject.toml` ワークフローをそのまま使うのがおすすめです。

```cmd
# Installation (using uv)
git clone --recurse-submodules https://github.com/moesnow/March7thAssistant
cd March7thAssistant
uv sync

# GUI を起動
uv run python app.py

# CLI ヘルプを表示
uv run python main.py -h

# 完全実行を開始
uv run python main.py

# デイリー訓練を実行
uv run python main.py daily
```

<details>
<summary>開発関連</summary>

crop パラメータで使う切り抜き座標は、ツールボックスのスクリーンショット機能で取得できます。

</details>

---

このプロジェクトが気に入ったら、WeChat で作者にコーヒーをご馳走できます ☕

支援は開発と保守の大きな助けになります。

![sponsor](assets/app/images/sponsor.jpg)

---

## 関連プロジェクト

March7thAssistant は以下のオープンソースプロジェクトおよび実行時依存に支えられています。保守者と貢献者の皆さんに感謝します。

- 模擬宇宙自動化 [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe): 模擬宇宙関連機能を提供
- フィールド探索自動化 [https://github.com/linruowuyin/Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail): 鋤大地関連機能を提供
- OCR 文字認識 [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR): ゲーム内文字認識を提供
- GUI コンポーネントライブラリ [https://github.com/zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets): 主要な UI コンポーネントと操作体験を提供
- Mirror酱 [https://github.com/MirrorChyan/docs](https://github.com/MirrorChyan/docs): 更新確認、配布、CDN 加速関連機能を提供
- 画像処理と自動化関連依存 `OpenCV`、`PyAutoGUI` など: スクリーンショット取得、画像処理、基本的な自動化を提供
- 推論高速化関連依存 `ONNX Runtime`、`OpenVINO`: OCR とモデル推論に CPU / GPU 高速化を提供

このほかにも `requirements.txt` には多くの低レベル依存が含まれています。ここに挙げていないプロジェクトにも感謝します。

## Contributors
<a href="https://github.com/moesnow/March7thAssistant/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=moesnow/March7thAssistant" />

</a>

## Stargazers over time

[![Star History](https://starchart.cc/moesnow/March7thAssistant.svg?variant=adaptive)](https://starchart.cc/moesnow/March7thAssistant)
