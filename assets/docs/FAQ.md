# 자주 묻는 질문 (FAQ)

영상 튜토리얼 [https://search.bilibili.com/all?keyword=三月七小助手](https://search.bilibili.com/all?keyword=%E4%B8%89%E6%9C%88%E4%B8%83%E5%B0%8F%E5%8A%A9%E6%89%8B)

### Q: 어시스턴트 업데이트가 항상 실패하거나 다운로드 속도가 느립니다. 어떡하죠?

A: March7thAssistant는 타사 서비스인 [Mirrorchyan](https://mirrorchyan.com/?source=m7a-faq)(오픈 소스 커뮤니티를 위한 유료 콘텐츠 배포 플랫폼)과 연동되어 있습니다.

이 서비스는 무료 업데이트 확인 인터페이스를 제공하지만, 다운로드 자체는 유료이며 사용자의 결제가 필요합니다.

하지만 Mirrorchyan 다운로드 서비스를 구매하지 않더라도, 업데이트 감지 후 설정에서 **해외 소스(GitHub)**를 선택하여 다운로드할 수 있습니다~

만약 CDK를 구매하여 입력했다면, 업데이트 시 네트워크 환경과 씨름할 필요 없이 더 빠르고 안정적으로 다운로드할 수 있습니다!

또한 CDK는 MAA 등 Mirrorchyan에 연동된 다른 프로젝트에서도 사용할 수 있습니다.

[(중국 본토 사용자용) 첫 다운로드라면 여기를 클릭하여 Mirrorchyan 고속 다운로드로 이동](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-faq)

### Q: 어시스턴트 실행이 느리거나 오류 코드 2147942402가 뜹니다 / 백신 프로그램이 자꾸 삭제합니다.

A: `March7thAssistant 폴더`를 백신 프로그램의 제외 항목/화이트리스트/신뢰 구역에 추가한 뒤, `March7th Updater.exe`를 사용하여 자동 업데이트하거나 수동으로 한 번 업데이트해 주세요.

Windows Defender(윈도우 디펜더): `바이러스 및 위협 방지` → `설정 관리` → `제외 항목 추가 또는 제거` (참고: [#373](https://github.com/moesnow/March7thAssistant/issues/373) 이미지 설명)

Huorong(중국 백신): `메인 화면` → `우측 상단 메뉴` → `신뢰 구역` (참고: [튜토리얼](https://cs.xunyou.com/html/282/15252.shtml) 이미지 설명)

### Q: 듀얼(다중) 모니터 사용 시 인식 오류 등 기타 문제가 발생합니다.

A: 설정 - 기타 - '다중 모니터에서 스크린샷 캡처(Screen capture on multi-monitors)' 옵션을 켜거나 꺼보세요.

관련 토론: [#383](https://github.com/moesnow/March7thAssistant/issues/383) [#710](https://github.com/moesnow/March7thAssistant/issues/710)

### Q: 자동 전투를 하지 않습니다.

A: 게임 내 설정 - 전투 기능 - '자동 전투 설정 유지'가 "예"로 되어 있는지 확인해 주세요.

### Q: 새로 추가된 던전이 없나요? 망각의 정원/허구 이야기(상시 콘텐츠)에 새 캐릭터가 없나요?

A: `던전 이름` 인터페이스에서 이름을 수동으로 입력하거나, `assets\config\instance_names.json` 파일을 편집하여 수동으로 추가할 수 있습니다.

망각의 정원 화면에서 어시스턴트 툴박스(도구 상자)의 `스크린샷 캡처(Capture Screenshot)` 기능을 사용해 캐릭터 얼굴을 선택하고 `선택한 스크린샷 저장`을 클릭한 후,

`assets\images\share\character` 폴더에 넣고 `assets\config\character_names.json` 파일을 수정하면 됩니다.

또한 압축 파일 등의 `무압축` 방식으로 [Issue](https://github.com/moesnow/March7thAssistant/issues)에 업로드하거나 [PR](https://github.com/moesnow/March7thAssistant/pulls)을 보내주시는 것도 환영합니다.

### Q: 전체 실행(Full Run)의 기능은 무엇인가요?

A: `일일` → `개척력 소모` → `필드 토벌` → `시뮬레이션 우주` → `망각의 정원/허구 이야기` → `보상 수령` 순서대로 실행됩니다.

이미 완료된 것으로 판단되는 작업은 반복 실행되지 않습니다. 일일 작업과 필드 토벌의 초기화 시간은 매일 새벽 4시이며,

시뮬레이션 우주와 망각의 정원/허구 이야기 등의 초기화 시간은 매주 월요일 새벽 4시입니다.

### Q: 실행을 시작하면 키보드/마우스를 움직이거나 백그라운드로 전환할 수 없나요?

A: 네, 그렇습니다. 백그라운드 실행이 필요한 경우 [원격 로컬 멀티 유저 데스크톱](https://m7a.top/#/assets/docs/Background)을 시도해 보세요.

### Q: 사용자 정의 알림을 추가하는 방법

A: 그래픽 인터페이스(GUI) 내에서는 `Windows 기본 알림` 활성화만 지원하며, 다른 알림이 필요한 경우 `config.yaml` 파일에서 활성화해야 합니다.

### Q: 시뮬레이션 우주에서 세계 단계, 캐릭터, 운명의 길, 난이도를 수정할 수 있나요?

A: 세계와 캐릭터는 한 번 선택해서 진입했다가 나오면 설정됩니다. 운명의 길과 난이도는 설정에서 시뮬레이션 우주를 찾아 `원본 실행`을 클릭한 뒤, 표시되는 그래픽 인터페이스 내에서 수정할 수 있습니다.

### Q: 시뮬레이션 우주 기타 문제

A: 빠른 시작 가이드: [프로젝트 문서](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md) 

문제 해결: 질문하기 전에 확인해 주세요: [Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)

### Q: 필드 토벌(토벌런)이 멈춰서 움직이지 않거나, 비정상적으로 작동합니다.

A: 잠금 해제되지 않은 텔레포트(경계의 닻), 맵의 문, 완료하지 않은 기관새 임무 등이 있는지 확인해 주세요.

### Q: 필드 토벌이 도중에 중단되었는데, 지정한 맵부터 실행하려면 어떻게 하나요?

A: 설정에서 필드 토벌을 찾아 `원본 실행`을 클릭하고, 디버그 모드를 선택하면 맵을 선택할 수 있습니다.