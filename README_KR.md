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
🌟 오른쪽 위의 Star를 누르면 Github 메인에서 업데이트 알림을 받을 수 있습니다.
</div>

<div align="center">
    <img src="assets/screenshot/star.gif" alt="Star" width="186" height="60">
</div>

<br/>

<div align="center">

[简体中文](./README.md) | [繁體中文](./README_TW.md) | [English](./README_EN.md) | [日本語](./README_JA.md) | **한국어**

**이 문서는 중국어 간체 원문을 기준으로 AI가 번역했습니다. 마지막 업데이트: 2026-04-24. 차이가 있으면 중국어 간체 원문을 우선해 주세요.**

**게임 내 언어는 현재 중국어 간체만 지원합니다.**

빠르게 시작하려면: [사용 튜토리얼](https://m7a.top/#/assets/docs/Tutorial_ko)

문제가 생기면 먼저 확인하세요: [FAQ](https://m7a.top/#/assets/docs/FAQ_ko)

</div>

## 기능 소개

- **일상**: 개척력 소모, 일일 훈련, 보상 수령, 위탁, 필드 파밍
- **주간**: 전쟁의 여운, 화폐 전쟁, 차분 우주, 혼돈의 기억, 허구 이야기, 종말의 환영
- **클라우드 스타레일**: 백그라운드 실행, 무창 실행, Docker 실행 지원
- **가챠 기록 내보내기**: [UIGF](https://uigf.org/zh/standards/uigf.html) / [SRGF](https://uigf.org/zh/standards/srgf.html) 표준 지원
- **도구 상자**: 자동 대화, FPS 잠금 해제, 리딤 코드
- 일일 훈련 등 작업 완료 여부에 대한 **메시지 푸시** 지원
- 작업 갱신 또는 개척력 회복 시점의 **자동 시작** 지원
- 작업 완료 후 **알림음, 게임 자동 종료, 시스템 종료 등** 지원

자세한 내용은 GUI 설정 또는 [설정 파일](assets/config/config.example.yaml)을 참고하세요 ｜ QQ 그룹 [바로가기](https://qm.qq.com/q/C3IryUWCQw) TG 그룹 [바로가기](https://t.me/+ZgH5zpvFS8o0NGI1) Bilibili [바로가기](https://space.bilibili.com/3706960664857075)

## 화면 예시

![README](assets/screenshot/README.png)

## 참고 사항

- 문제가 생기면 [Issue](https://github.com/moesnow/March7thAssistant/issues)에 남겨 주세요. 질문이나 토론은 [Discussions](https://github.com/moesnow/March7thAssistant/discussions)에서 진행해 주세요. 채팅방은 수시로 확인하지 않습니다.
- [PR](https://github.com/moesnow/March7thAssistant/pulls) 환영합니다. 제출 전 [기여 가이드](CONTRIBUTING.md)를 읽어 주세요.

## 다운로드 및 설치

[Releases](https://github.com/moesnow/March7thAssistant/releases/latest)에서 최신 버전을 내려받아 압축을 푼 뒤, 3월 7일 아이콘이 있는 `March7th Launcher.exe`를 더블 클릭해 GUI를 실행하세요.

## 소스 실행

완전 초보라면 위의 배포판 사용을 권장합니다. 아래 내용은 건너뛰어도 됩니다.

Python 3.12 이상을 권장합니다.

Windows에서 터미널로 실행할 경우 PowerShell, Windows Terminal, CMD를 관리자 권한으로 여는 것을 권장합니다. Windows 11 24H2 이상에서는 [Sudo for Windows](https://learn.microsoft.com/zh-cn/windows/advanced-settings/sudo/)도 사용할 수 있습니다.

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

`uv`를 사용한다면 프로젝트에 포함된 `pyproject.toml` 워크플로를 그대로 쓰는 것을 권장합니다.

```cmd
# Installation (using uv)
git clone --recurse-submodules https://github.com/moesnow/March7thAssistant
cd March7thAssistant
uv sync

# GUI 실행
uv run python app.py

# CLI 도움말 보기
uv run python main.py -h

# 전체 실행
uv run python main.py

# 일일 훈련 실행
uv run python main.py daily
```

<details>
<summary>개발 관련</summary>

crop 매개변수에 쓰이는 자르기 좌표는 도구 상자의 캡처 스크린샷 기능으로 확인할 수 있습니다.

</details>

---

이 프로젝트가 마음에 들면 WeChat으로 개발자에게 커피 한 잔을 후원할 수 있습니다 ☕

여러분의 후원은 프로젝트 개발과 유지보수의 큰 힘이 됩니다.

![sponsor](assets/app/images/sponsor.jpg)

---

## 관련 프로젝트

March7thAssistant는 다음 오픈소스 프로젝트와 런타임 의존성의 도움을 받고 있습니다. 모든 유지보수자와 기여자에게 감사드립니다.

- 시뮬레이션 우주 자동화 [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe): 시뮬레이션 우주 관련 기능 제공
- 필드 파밍 자동화 [https://github.com/linruowuyin/Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail): 필드 파밍 관련 기능 제공
- OCR 문자 인식 [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR): 게임 내 문자 인식 제공
- GUI 컴포넌트 라이브러리 [https://github.com/zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets): 주요 UI 컴포넌트와 상호작용 경험 제공
- Mirror짱 [https://github.com/MirrorChyan/docs](https://github.com/MirrorChyan/docs): 업데이트 확인, 다운로드 배포, CDN 가속 관련 기능 제공
- 이미지 처리 및 자동화 관련 의존성 `OpenCV`, `PyAutoGUI` 등: 스크린샷 수집, 이미지 처리, 기본 자동화 기능 제공
- 추론 가속 관련 의존성 `ONNX Runtime`, `OpenVINO`: OCR 및 모델 추론에 CPU / GPU 가속 제공

또한 `requirements.txt`에는 여기서 일일이 열거하지 않은 많은 하위 의존성이 포함되어 있습니다. 이 프로젝트들을 포함한 모든 지원에도 감사드립니다.

## Contributors
<a href="https://github.com/moesnow/March7thAssistant/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=moesnow/March7thAssistant" />

</a>

## Stargazers over time

[![Star History](https://starchart.cc/moesnow/March7thAssistant.svg?variant=adaptive)](https://starchart.cc/moesnow/March7thAssistant)
