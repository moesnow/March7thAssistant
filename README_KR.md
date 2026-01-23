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
🌟 우측 상단의 Star를 눌러두시면 Github 메인에서 업데이트 알림을 받을 수 있습니다!
</div>

<div align="center">
    <img src="assets/screenshot/star.gif" alt="Star" width="186" height="60">
  </a>
</div>

<br/>

<div align="center">

[简体中文](./README.md) | [繁體中文](./README_TW.md) | [English](./README_EN.md) | [日本語](./README_JA.md) | **한국어**

**게임 내 언어는 간체 중국어만 지원하지만, 프로그램 인터페이스는 한국어와 영어를 지원합니다.**

**반드시 게임 내 언어는 중국어로 설정해야 합니다.**

시작하려면, 다음을 방문하세요: [사용 튜토리얼](https://m7a.top/#/assets/docs/Tutorial)

문제가 발생하면 질문하기 전에 먼저 확인하세요: [FAQ](https://m7a.top/#/assets/docs/FAQ)

</div>

## 기능 소개

- **일일 숙제**: 개척력 소모, 일일 훈련, 보상 수령, 의뢰, 토벌(필드 파밍)
- **주간 숙제**: 전쟁의 여운, 화폐 전쟁, 시뮬레이션 우주, 망각의 정원
- **가챠 기록 내보내기**: [UIGF](https://uigf.org/zh/standards/uigf.html)/[SRGF](https://uigf.org/zh/standards/srgf.html) 표준 지원, **자동 대화**
- 일일 훈련 등 임무 완료 시 **푸시 알림** 지원
- 임무가 초기화되거나 개척력이 지정된 값까지 회복되면 **자동 시작**
- **다국어 지원**: 한국어 및 영어 인터페이스 지원 (설정에서 변경 가능)
- 임무 완료 후 **알림음 재생, 게임 자동 종료 또는 컴퓨터 종료 등**

> 시뮬레이션 우주는 [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) 프로젝트를, 토벌은 [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 프로젝트를 호출하여 사용합니다.

자세한 내용은 [설정 파일](assets/config/config.example.yaml) 또는 GUI 설정을 참고하세요. ｜QQ 그룹 [클릭하여 이동](https://qm.qq.com/q/C3IryUWCQw) TG 그룹 [클릭하여 이동](https://t.me/+ZgH5zpvFS8o0NGI1)

## 인터페이스 예시

![README](assets/screenshot/README.png)

## 주의사항

- 반드시 **PC** 해상도 `1920*1080` 창 모드 또는 전체 화면으로 게임을 실행해야 합니다 (HDR 미지원).
- **macOS** 및 **Linux** 지원 (클라우드 게임 모드 한정), [Docker 배포](https://m7a.top/#/assets/docs/Docker)도 지원합니다.
- 시뮬레이션 우주 관련 내용은 [프로젝트 문서](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md) 및 [Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)를 참고하세요.
- 백그라운드 실행이나 다중 모니터 환경이 필요한 경우 [원격 로컬 다중 사용자 데스크톱](https://m7a.top/#/assets/docs/Background)을 시도해 볼 수 있습니다.
- 오류가 발생하면 [Issue](https://github.com/moesnow/March7thAssistant/issues)에 피드백을 남겨주세요. 질문이나 토론은 [Discussions](https://github.com/moesnow/March7thAssistant/discussions)에서 가능합니다. (채팅방은 확인이 늦을 수 있습니다)
- [PR](https://github.com/moesnow/March7thAssistant/pulls) 환영합니다. 제출 전 [기여 가이드](CONTRIBUTING.md)를 읽어주세요.

## 다운로드 및 설치

[Releases](https://github.com/moesnow/March7thAssistant/releases/latest)로 이동하여 다운로드 후 압축을 풀고, March 7th(삼칠이) 아이콘인 `March7th Launcher.exe`를 더블 클릭하여 그래픽 인터페이스를 엽니다.

**작업 스케줄러**를 사용하여 예약 실행하거나 **전체 실행**을 바로 수행하려면, 터미널 아이콘인 `March7th Assistant.exe`를 사용할 수 있습니다.

업데이트 확인은 그래픽 인터페이스 설정 최하단의 버튼을 클릭하거나 `March7th Updater.exe`를 더블 클릭하세요.

### 명령줄 인수

그래픽 인터페이스 `March7th Launcher.exe`는 명령줄 인수를 지원하여 실행 시 지정된 작업을 자동으로 수행할 수 있습니다:

```bash
# 도움말 보기
March7th Launcher.exe -h

# 사용 가능한 모든 작업 나열
March7th Launcher.exe -l

# 그래픽 인터페이스 실행 및 전체 실행
March7th Launcher.exe main

# 그래픽 인터페이스 실행 및 일일 훈련 수행
March7th Launcher.exe daily

# 작업이 정상적으로 완료되면 자동 종료 (작업 인수와 함께 사용)
March7th Launcher.exe main -e
```

<details>
<summary>사용 가능한 작업 목록</summary>

| 작업 이름 | 설명 |
|---------|------|
| main | 전체 실행 |
| daily | 일일 훈련 |
| power | 개척력 소모 |
| currencywars | 화폐 전쟁 |
| currencywarsloop | 화폐 전쟁 반복 |
| fight | 토벌 (필드 파밍) |
| universe | 시뮬레이션 우주 |
| forgottenhall | 혼돈의 기억 |
| purefiction | 허구 이야기 |
| apocalyptic | 종말의 환영 |
| redemption | 리딤코드 교환 |
| universe_gui | 시뮬레이션 우주 (원본 GUI) |
| fight_gui | 토벌 (원본 GUI) |
| universe_update | 시뮬레이션 우주 업데이트 |
| fight_update | 토벌 업데이트 |
| game | 게임 시작 |
| notify | 알림 테스트 |

</details>

## 소스 코드 실행

완전한 초보자라면 위에서 언급한 다운로드 및 설치 방법을 사용해 주세요.

Python 3.12 이상의 버전을 권장합니다.

```cmd
# 설치 (가상 환경(venv) 사용 권장)
git clone --recurse-submodules https://github.com/moesnow/March7thAssistant
cd March7thAssistant
pip install -r requirements.txt
python app.py
python main.py

# 업데이트
git pull
git submodule update --init --recursive
```

<details>
<summary>개발 관련</summary>

crop 매개변수로 표시되는 자르기 좌표는 도우미 도구 상자 내의 스크린샷 캡처 기능을 통해 얻을 수 있습니다.

`python main.py` 실행 뒤에 "fight", "universe", "forgottenhall" 등의 매개변수를 추가할 수도 있습니다.

</details>

---

이 프로젝트가 마음에 드신다면, 개발자에게 커피 한 잔을 후원해 주세요 ☕

여러분의 후원은 프로젝트 개발과 유지보수의 원동력이 됩니다. 🚀

![sponsor](assets/app/images/sponsor.jpg)

---

## 관련 프로젝트

March7thAssistant는 다음 오픈 소스 프로젝트들의 도움 없이는 불가능했을 것입니다:

- 시뮬레이션 우주 자동화 [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe)

- 토벌(필드 파밍) 자동화 [https://github.com/linruowuyin/Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail)

- OCR 텍스트 인식 [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)

- 그래픽 인터페이스 컴포넌트 라이브러리 [https://github.com/zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)


## Contributors
<a href="https://github.com/moesnow/March7thAssistant/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=moesnow/March7thAssistant" />

</a>

## Stargazers over time

[![Star History](https://starchart.cc/moesnow/March7thAssistant.svg?variant=adaptive)](https://starchart.cc/moesnow/March7thAssistant)
