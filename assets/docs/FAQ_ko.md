# 자주 묻는 질문

동영상 튜토리얼 [https://search.bilibili.com/all?keyword=三月七小助手](https://search.bilibili.com/all?keyword=%E4%B8%89%E6%9C%88%E4%B8%83%E5%B0%8F%E5%8A%A9%E6%89%8B) (중국어)

### Q: 어시스턴트 업데이트가 자주 실패하거나 다운로드 속도가 너무 느려요.

A: March7thAssistant는 오픈소스 커뮤니티를 위한 유료 콘텐츠 배포 플랫폼인 [Mirror 짱](https://mirrorchyan.com/?source=m7a-faq)과 연동되어 있습니다.

Mirror 짱은 무료 업데이트 확인 기능을 제공하지만, 고속 다운로드는 유료 서비스입니다.

하지만 유료 서비스를 이용하지 않더라도, 업데이트 감지 후 **설정**에서 다운로드 소스를 **'해외 소스(GitHub)'**로 변경하면 무료로 다운로드할 수 있습니다.

만약 CDK를 구매하여 입력한다면 네트워크 환경에 구애받지 않고 빠르고 안정적인 업데이트가 가능합니다! 또한 CDK는 MAA 등 Mirror 짱을 사용하는 다른 프로젝트에서도 공용으로 사용할 수 있습니다.

[Mirror 짱에서 고속으로 다운로드하기](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-faq)

### Q: 어시스턴트 실행이 느리거나, 실행 파일이 없다거나, 2147942402 오류가 뜨거나, 백신이 자꾸 파일을 삭제해요.

A: `어시스턴트 폴더`를 백신 프로그램의 **제외 항목(화이트리스트/신뢰 영역)**에 추가한 뒤, 압축을 다시 풀어서 덮어씌워 주세요.

Windows Defender: `바이러스 및 위협 방지` → `설정 관리` → `제외` → `제외 사항 추가 또는 제거` ([참고 이미지 #373](https://github.com/moesnow/March7thAssistant/issues/373))

(추가로 `앱 및 브라우저 컨트롤` → `스마트 앱 제어 설정` → `끄기`가 필요할 수도 있습니다.)

Huorong(화롱) 보안: `메인 화면` → `우측 상단 메뉴` → `신뢰 영역` ([튜토리얼](https://cs.xunyou.com/html/282/15252.shtml))

### Q: 듀얼(다중) 모니터 사용 중인데 인식이 잘 안 되거나 문제가 생겨요.

A: **설정 - 기타 - 다중 모니터 상에서 스크린샷 캡처** 옵션을 켜거나 꺼보세요.

관련 논의: [#383](https://github.com/moesnow/March7thAssistant/issues/383) [#710](https://github.com/moesnow/March7thAssistant/issues/710)

### Q: 자동 전투가 안 켜져요.

A: 게임 내 **설정 - 전투 기능 - 자동 전투 설정 유지** 옵션이 **"예"**로 되어 있는지 확인해 주세요.

### Q: 새로 나온 던전이나 캐릭터가 목록에 없어요.

A: `던전 이름` 설정에서 직접 이름을 입력하거나, `assets\config\instance_names.json` 파일을 열어 수동으로 추가할 수 있습니다.

캐릭터의 경우, '망각의 정원' 화면에서 어시스턴트 도구함의 `스크린샷 캡처` 기능을 이용해 캐릭터 얼굴 부분을 선택하고 `선택한 스크린샷 저장`을 누르세요.
그 후 `assets\images\share\character` 폴더에 이미지를 넣고 `assets\config\character_names.json` 파일을 수정하면 됩니다.

혹은 이미지를 `압축하지 말고`(압축 파일 권장) [Issue](https://github.com/moesnow/March7thAssistant/issues)에 올려주시거나 [PR](https://github.com/moesnow/March7thAssistant/pulls)을 보내주시면 더 좋습니다.

### Q: '전체 실행'은 정확히 뭘 하는 건가요?

A: `일일` → `개척력(던전)` → `필드 정리` → `시뮬레이션 우주` → `상시 도전` → `보상 수령` 순서로 모든 작업을 일괄 처리합니다.

이미 완료되었다고 판단된 작업은 건너뜁니다.
'일일 임무'와 '필드 정리'는 매일 새벽 4시에 리셋되며,
'시뮬레이션 우주'와 '상시 도전'은 매주 월요일 새벽 4시에 리셋됩니다.

### Q: 실행 중에 키보드/마우스를 쓰거나 백그라운드로 보내면 안 되나요?

A: 네, 화면을 점유해야 합니다. 백그라운드 실행이 필요하다면 [원격 로컬 멀티 데스크톱](https://m7a.top/#/assets/docs/Background) 기능을 활용해 보세요.

### Q: 나만의 알림(Custom Notification)은 어떻게 추가하나요?

A: 프로그램 설정 화면에서는 `Windows 기본 알림`만 켜고 끌 수 있습니다.
다른 알림 방식은 `config.yaml` 파일을 직접 수정하여 활성화해야 합니다.

### Q: 시뮬레이션 우주 세계, 캐릭터, 운명의 길, 난이도는 어떻게 바꾸나요?

A: 세계와 캐릭터는 게임 내에서 한 번 진입했다가 나오면 설정됩니다.
운명의 길과 난이도는 설정에서 '시뮬레이션 우주' 항목을 찾아 `원본 실행`을 클릭한 뒤, 나오는 그래픽 인터페이스에서 변경할 수 있습니다.

### Q: 시뮬레이션 우주 관련 다른 문제가 있어요.

A: 빠른 시작 가이드: [프로젝트 문서](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md)

질문하기 전 확인: [Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)

### Q: 필드 정리가 자꾸 멈추거나 이상하게 동작해요.

A: 맵에 아직 안 찍은 텔레포트 포인트가 있거나, 문을 열어야 하거나, 기계 새 퍼즐을 안 푼 곳이 있는지 확인해 주세요.

### Q: 필드 정리가 중간에 멈췄는데, 특정 맵부터 다시 할 수 있나요?

A: 설정에서 '필드 정리'의 `원본 실행`을 클릭하세요. Fhoe-Rail 창이 뜨면 '디버그 모드'를 체크하고 원하는 맵을 선택해서 시작할 수 있습니다.
