# 업데이트 내역

## v2025.12.29-beta
- HoYoPlay(미호요 런처)를 통한 게임 자동 업데이트 지원
- 테마 변경 후 트레이 영역에서 복원 시 인터페이스를 다시 로드해야 하는 문제 수정

## v2025.12.26
- 예약 실행에 다중 작업 및 외부 프로그램 추가 지원
- 리딤코드를 찾지 못했을 때의 처리 로직 최적화
- 클라우드 게임 설정에서 허용되는 최대 대기 시간 범위 조정
- B서버(비리비리 서버) 로그인 UI 변경으로 인한 실행 오류 수정
- 일부 상황에서 일일 훈련 보상 수령이 미완료로 잘못 보고되는 문제 수정 [#820](https://github.com/moesnow/March7thAssistant/pull/820) @g60cBQ
- 육성 목표가 던전을 인식하지 못한 경우에도 계속 실행되는 문제 수정 [#819](https://github.com/moesnow/March7thAssistant/pull/819) @g60cBQ

## v2025.12.21
- 다알리아 및 Mar. 7th·겨울이 가고 봄이 오면 스킨 지원 [#813](https://github.com/moesnow/March7thAssistant/pull/813) @loader3229
- 업적 보상 수령 기능 추가 [#811](https://github.com/moesnow/March7thAssistant/pull/811) @g60cBQ
- 리딤코드 자동 획득 및 수령 기능 추가
- 터치스크린 모드 기능 지원 복구
- 예약 실행 작업의 트리거 로직 최적화
- 화폐 전쟁(이벤트) 미정산 대국 처리 지원 최적화
- 전체 설치 패키지에 클라우드 게임 전용 브라우저 내장 [#815](https://github.com/moesnow/March7thAssistant/pull/815) @Patrick16262
- 복귀 유저가 이벤트 페이지를 올바르게 인식하지 못하는 문제 수정
- 특정 상황에서 개척력 계획(Stamina Plan)이 잘못 판단하여 실행되지 않는 문제 수정
- 육성 계획 활성화 후 던전 연속 도전 횟수 오류 수정
- 클라우드·붕괴: 스타레일 백그라운드 실행 시 클립보드가 작동하지 않는 문제 수정 [#816](https://github.com/moesnow/March7thAssistant/pull/816) @Patrick16262
- 클라우드 게임 사용 시 필드 토벌(토벌런) 빠른 시작이 불가능한 문제 수정

## v2025.12.16
- 로그 인터페이스 신규 추가 및 작업 실행 방식 최적화
- 그래픽 인터페이스(GUI) 터치 스크롤 지원 추가 [#799](https://github.com/moesnow/March7thAssistant/pull/799) @g60cBQ
- 그래픽 인터페이스 시스템 트레이로 최소화 지원
- 클라우드 게임 다운로드 시 국내(중국) 미러 소스 가속 사용 [#792](https://github.com/moesnow/March7thAssistant/pull/792) @Patrick16262
- 클라우드 게임 관련 여러 문제 최적화 및 수정 [#800](https://github.com/moesnow/March7thAssistant/pull/800) [#804](https://github.com/moesnow/March7thAssistant/pull/804) @Patrick16262
- WebHook 푸시 알림 설정 항목 추가 최적화
- 자동 테마 기능이 정상 작동하지 않는 문제 수정
- 차분화 우주 포인트 보상 실행 시 카테고리 선택 오류 수정
- 언어가 중국어가 아닐 때 로그 인터페이스 표시 이상 수정

## v2025.12.13

- 개척력 계획(Stamina Plan) 지원
- 설정 인터페이스 최적화
- 2배 이벤트에서 육성 계획 읽기 지원 [#751](https://github.com/moesnow/March7thAssistant/pull/751) @g60cBQ
- 이제 일일 훈련 완료 판단 후 즉시 보상을 수령합니다
- 장신구 추출 시 캐릭터가 설정되지 않은 경우 자동으로 첫 번째 파티 선택 [#788](https://github.com/moesnow/March7thAssistant/pull/788) @g60cBQ
- 프레임 잠금 해제 및 해상도 자동 수정 기능 국제 서버(Global) 호환
- 설정 파일 변경 시 그래픽 인터페이스 자동 새로고침

## v2025.12.10

- 화폐 전쟁 관련 여러 문제 최적화 및 수정
- 던전 이름 및 파티 캐릭터 수동 입력 및 실시간 자동 완성 지원
- 알림 레벨 설정 지원 (예: 오류 알림만 푸시)
- 푸시 알림 전송 전 스크린샷 압축으로 용량 감소
- KOOK, WebHook 푸시 지원 추가
- Bark 푸시 암호화 지원 추가
- 30일 이상 된 로그 파일 자동 정리 기능 추가

## v2025.12.8

- 화폐 전쟁 지원
- 화폐 전쟁 관련 여러 이상 문제 수정
- 워프(뽑기) 기록 UIGF 형식 가져오기 및 내보내기 지원
- 개척력 소모 전 임의의 닻(텔레포트)으로 이동 [#760](https://github.com/moesnow/March7thAssistant/pull/760) @Xuan-cc
- 클라우드 게임 관련 여러 문제 최적화 및 수정 [#763](https://github.com/moesnow/March7thAssistant/pull/763) @Patrick16262
- 작업 완료 후 모니터 끄기 지원 추가
- 워프 기록 삭제 시 2차 확인 팝업 추가
- 육성 목표의 고치(Calyx) 던전 정보 추출 실패 수정 [#764](https://github.com/moesnow/March7thAssistant/pull/764) @g60cBQ
- 작업 완료 후 ps1 스크립트 실행 실패 수정 [#759](https://github.com/moesnow/March7thAssistant/pull/759) @0frostmourne0

## v2025.12.1

- 클라우드·붕괴: 스타레일 지원 [#750](https://github.com/moesnow/March7thAssistant/pull/750)
- 육성 목표에 따른 동적 던전 선택 지원 [#751](https://github.com/moesnow/March7thAssistant/pull/751)
- 일일 훈련 시 임무 완료 상황을 읽고 작업 실행 조정 [#753](https://github.com/moesnow/March7thAssistant/pull/753)
- 기업용 위챗(WeChatWork) 봇 푸시 방식 이미지 전송 지원 [#742](https://github.com/moesnow/March7thAssistant/pull/742)
- 특정 상황에서 빛 따라 금 찾아(逐光捡金) 시 캐릭터 선택 실패 수정 [#747](https://github.com/moesnow/March7thAssistant/pull/747)
- 작업 완료 후 스크립트 선택 시 튕김 현상 수정
- 간헐적으로 게임 프로세스가 정상 종료되지 않는 문제 수정
- UI 변화로 인한 차분화 우주 및 시뮬레이션 우주 자동 전투 감지 이상 수정
- 전체 실행 시 작업 실행 순서 최적화
- 업데이트 프로그램의 일부 문제 최적화
- 자동 로그인 프로세스 최적화

## v2025.11.11

- "차분화 우주 1회 우선 실행" 작업 주기를 2주 1회로 업데이트
- SMTP 알림 발송 시 사용자 이름 미사용 지원 [#730](https://github.com/moesnow/March7thAssistant/pull/730) [#738](https://github.com/moesnow/March7thAssistant/pull/738)
- 3.7 신규 주간 보스(전쟁의 여운) 인식 이상 수정 [#728](https://github.com/moesnow/March7thAssistant/pull/728)
- 리딤코드 입력창 인식 이상 수정 [#734](https://github.com/moesnow/March7thAssistant/pull/734)
- 특정 조건에서 지원 캐릭터 선택 화면 클릭 이상 수정

## v2025.11.6

- 3.7 버전 신규 스테이지 및 캐릭터 지원 [#725](https://github.com/moesnow/March7thAssistant/pull/725)
- 일부 던전 유형 연속 도전 지원 추가
- 자동 대화 도구 리팩토링: 설정 옵션 추가 및 문제 수정 [#720](https://github.com/moesnow/March7thAssistant/pull/720)
- FAQ(자주 묻는 질문)에 다중 모니터 관련 문제 및 해결책 추가
- 다계정 로그인 화면 멈춤 문제 수정 [#723](https://github.com/moesnow/March7thAssistant/pull/723)
- 시뮬레이션 우주 진입 UI 변화로 인한 이상 수정
- 이벤트 화면 UI 변화로 인한 이상 수정
- 차분화 우주 지원 UI 변화로 인한 이상 수정
- 전쟁의 여운 실행 요일이 설정 화면에 잘못 표시되는 문제 수정
- 그래픽 인터페이스 레이아웃 최적화

## v2025.10.15

- 3.6 버전 신규 캐릭터 지원
- 자동 로그인 과정 최적화 및 국제 서버(Global) 호환 [#706](https://github.com/moesnow/March7thAssistant/pull/706)
- 파티원 사망 시 던전 도전 계속 진행 지원 [#705](https://github.com/moesnow/March7thAssistant/pull/705)
- 일부 타임아웃 시간 지연을 통해 HDD 사용 경험 최적화 [#701](https://github.com/moesnow/March7thAssistant/pull/701)
- "성공 후 프로그램 일시 정지" 및 "실패 후 즉시 종료" 옵션 추가 [#704](https://github.com/moesnow/March7thAssistant/pull/704) [#709](https://github.com/moesnow/March7thAssistant/pull/709)
- 일부 사용자에게 발생할 수 있는 다운로드 이상 수정
- 다운로더가 시스템 프록시를 자동 사용하도록 최적화
- 설정 파일 초기화 기능의 오류 메시지 최적화

## v2025.9.25

- 3.6 버전 신규 스테이지 및 캐릭터 지원
- 일일 "합성 재료" 흐름 최적화 및 설정에서 끄기 지원
- "지원 목록" 친구 이름을 비워둘 경우 선택한 캐릭터만 검색 지원
- 지원 캐릭터 "선데이" 설정 후 간헐적으로 친구 이름 인식 이상 수정
- "워프 기록" 데이터 업데이트 시 간헐적 튕김 수정
- "사용자 로그인 시 시작" 옵션 설명 최적화
- 여러 던전 이름 인식 오류 수정

## v2025.9.10

- 3.5 버전 신규 스테이지 및 캐릭터 지원 [#687](https://github.com/moesnow/March7thAssistant/pull/687)
- 여러 던전 이름 인식 오류 수정
- 우편함 인식 이상 수정

## v2025.8.13

- 3.5 버전 신규 스테이지 및 캐릭터 지원 [#671](https://github.com/moesnow/March7thAssistant/pull/671)
- 여러 던전 이름 인식 오류 수정

## v2025.7.20

- Fate 콜라보 캐릭터 지원 [#640](https://github.com/moesnow/March7thAssistant/pull/640)
- 워프 기록 콜라보 워프 지원
- 지도 및 워프 키 설정 변경 지원 추가 [#635](https://github.com/moesnow/March7thAssistant/pull/635)
- "자동 대화" 기능에 "대화 자동 스킵" 지원 [#639](https://github.com/moesnow/March7thAssistant/pull/639)
- 다계정 관리 기능 레지스트리 정리 지원 [#636](https://github.com/moesnow/March7thAssistant/pull/636)
- 차원 분열 이벤트로 인한 오류 수정 [#643](https://github.com/moesnow/March7thAssistant/pull/643)
- 시뮬레이션 우주 종료 시 발생하는 오류 수정
- 자동 대화가 선택지를 지원하지 않는 문제 수정

## v2025.7.8

- 3.4 버전 신규 스테이지 및 캐릭터 지원 [#616](https://github.com/moesnow/March7thAssistant/pull/616)
- "명족의 형상" 던전 진입 불가 수정

## v2025.6.14

- 3.3 버전 신규 스테이지 및 캐릭터 지원 [#580](https://github.com/moesnow/March7thAssistant/pull/580) [#597](https://github.com/moesnow/March7thAssistant/pull/597)
- 워프 기록을 Excel 파일로 내보내기 지원 [#574](https://github.com/moesnow/March7thAssistant/pull/574)
- 고치(Calyx) 매 회차 도전 횟수 수정 지원 [#592](https://github.com/moesnow/March7thAssistant/pull/592)
- 설정 페이지 슬라이더에 버튼을 추가하여 미세 조정 지원 [#591](https://github.com/moesnow/March7thAssistant/pull/591)
- 차분화 우주 일시 후퇴 이미지 수정 [#594](https://github.com/moesnow/March7thAssistant/pull/594)
- 워프 데이터에 이상이 있을 때 Excel 내보내기 실패 수정
- 일부 옵션으로 인한 그래픽 인터페이스 튕김 수정
- Gotify 푸시 이상 수정
- 시뮬레이션 우주(Auto_Simulated_Universe) v8.04
- Mirrorchyan을 통한 시뮬레이션 우주 업데이트 지원

## v2025.4.18

- 2주년 이벤트 아이콘 적용
- 아글라에아 지원 [#548](https://github.com/moesnow/March7thAssistant/pull/548)
- 전쟁의 여운(주간 보스) 실행 요일 설정 지원 [#479](https://github.com/moesnow/March7thAssistant/pull/479)
- 유물 수량이 상한에 도달하면 4성 유물 분해 우선 실행 [#524](https://github.com/moesnow/March7thAssistant/pull/524)
- OneBot 개인 메시지와 그룹 메시지 동시 전송 지원 [#540](https://github.com/moesnow/March7thAssistant/pull/540)
- 필드 토벌(토벌런) 옴팔로스 우선순위 설정 항목 추가 [#547](https://github.com/moesnow/March7thAssistant/pull/547)
- Mirrorchyan 사용 경험 최적화, CDK 만료 등 오류 팁 추가
- Lark(페이슈), Gotify, OneBot 푸시 수정 [#520](https://github.com/moesnow/March7thAssistant/pull/520) [#517](https://github.com/moesnow/March7thAssistant/pull/517)
- 모든 일일 임무 미완료 시 보상 수령이 올바르지 않은 문제 수정
- 시스템이 자동 테마를 지원하지 않을 때 발생하는 튕김 수정 [#525](https://github.com/moesnow/March7thAssistant/pull/525)
- 예약 작업 시간 로딩 시 로컬 지역 설정으로 인한 튕김 수정 [#512](https://github.com/moesnow/March7thAssistant/pull/512)

## v2025.3.7

- 시뮬레이션 우주(Auto_Simulated_Universe) 신규 버전 차분화 우주 적용
- 3.1 버전 신규 스테이지 및 캐릭터 지원 [#486](https://github.com/moesnow/March7thAssistant/pull/486)
- 작업 완료 후 지정된 프로그램 또는 스크립트 실행 지원 [#453](https://github.com/moesnow/March7thAssistant/pull/453)
- 매주 1회 차분화 우주 우선 실행 지원 (설정-우주)
- Mirrorchyan 타사 앱 배포 플랫폼 연동 (정보 → 업데이트 소스)
- 육성 목표 설정 후 일부 던전 이상 수정
- 일반 시뮬레이션 우주 인터페이스 진입 불가 수정
- 소모품 합성이 정상적으로 되지 않는 문제 수정 [#482](https://github.com/moesnow/March7thAssistant/issues/482)
- 터치스크린 모드 일시적 사용 불가 [#487](https://github.com/moesnow/March7thAssistant/issues/487)

## v2025.1.20

- 3.0 버전 신규 스테이지 및 캐릭터 지원 [#442](https://github.com/moesnow/March7thAssistant/pull/442)
- "Matrix" 푸시 방식 지원 [#440](https://github.com/moesnow/March7thAssistant/pull/440)
- 개척력 상한 300으로 수정 [#447](https://github.com/moesnow/March7thAssistant/pull/447)
- 몰입기 수량 인식 불가 수정 [#441](https://github.com/moesnow/March7thAssistant/issues/441)
- 워프 기록 업데이트 불가 수정
- 일부 코드 규범성 최적화 [#443](https://github.com/moesnow/March7thAssistant/pull/443)

## v2024.12.18

### 업데이트
- "차원 분열 활성화" 시 2배 횟수가 존재하면 개척력을 「장신구 추출」에 우선 사용
- 그래픽 인터페이스에서 모든 푸시 방식 온/오프 및 설정 수정 지원
- "프레임 잠금 해제" 및 "터치스크린 모드" 오류 메시지 최적화 (게임 화질을 사용자 정의로 변경 필요)
- "자동 전투 감지 활성화" 시 게임 시작 전 해당 레지스트리 값 검사 및 수정 시도

## v2024.12.12

### 업데이트
- "터치스크린 모드(클라우드 게임 모바일 UI)"로 게임 실행 지원 (도구 상자)
- "몰입 보상 수령" 옵션을 "몰입 보상 수령/장신구 추출 실행"으로 변경 (포인트 보상 수령 후 자동으로 장신구 추출 실행)
- 신규 배경화면 "꿈 없는 긴 밤" 변경 후 우편함 진입 불가 수정
- 종말의 환영 빠른 도전 팁 인식 및 건너뛰기 불가 수정 [#406](https://github.com/moesnow/March7thAssistant/issues/406) 

## v2.7.0

### 새로운 기능
- "선데이", "영사" 지원
- 종말의 환영 지원 [#397](https://github.com/moesnow/March7thAssistant/pull/397) 
- 부팅 후 자동 실행 지원 (설정-기타)
- 반복(Loop) 모드 매 실행 전 설정 파일 다시 로드
- "다중 모니터에서 스크린샷 캡처" 옵션 추가 (설정-기타) [#392](https://github.com/moesnow/March7thAssistant/pull/392) 
- 미호요 런처를 통해 설치된 게임 경로 자동 획득 지원
- 메인 프로그램 누락 시 오류 메시지 최적화

### 수정
- "일일 임무"가 매번 시작 시 잘못 초기화되는 문제
- "자동 대화" 상태가 변경되지 않거나 속도가 너무 느린 문제
- 캐릭터 프로필 매칭 임계값 낮춤 [#356](https://github.com/moesnow/March7thAssistant/issues/356)

## v2.6.3

### 새로운 기능
- 2.6 버전 신규 스테이지 및 캐릭터(라파) 지원
- "던전 이름" 설정 항목 수동 입력 지원
- 사망으로 인한 도전 실패 후 자동 재시도 지원 [#385](https://github.com/moesnow/March7thAssistant/pull/385)
- 리딤코드 일괄 자동 사용 지원 (도구 상자)
- "워프 기록"의 "전체 데이터 업데이트" 지원 (잘못된 워프 데이터 수정용)
- 반복(Loop) 모드에서 "개척력 기준"(기존) 및 "예약 작업"(지정 시간) 지원
- "ServerChan 3" 푸시 방식 지원 [#377](https://github.com/moesnow/March7thAssistant/pull/377)

### 수정
- 워프 기록 API 교체
- 수동으로 수정한 설정 파일이 그래픽 인터페이스에 의해 덮어씌워지는 문제 [#341](https://github.com/moesnow/March7thAssistant/issues/341) [#379](https://github.com/moesnow/March7thAssistant/issues/379)
- 게임 창이 다중 모니터 보조 화면에 있을 때 스크린샷이 검게 나오거나 좌표가 밀리는 문제 [#378](https://github.com/moesnow/March7thAssistant/pull/378) [#384](https://github.com/moesnow/March7thAssistant/pull/384)
- 다크 모드에서 프로그램 최초 실행 시 계정 목록 배경색 이상
- "꽃이 피는 정원" 이벤트가 있지만 활성화하지 않은 경우 무한 루프 진입 문제

## v2.5.4

### 새로운 기능
- 2.5 버전 신규 스테이지 지원
- 지원(Support) 기능 리메이크 (지정 친구의 지정 캐릭터 지원 및 장신구 추출 사용 지원, 재설정 필요)
- "비소", "초구", "맥택", "제이드" 지원
- B서버 실행 후 "로그인" 자동 클릭 지원 [#321](https://github.com/moesnow/March7thAssistant/discussions/321)
- "작업 완료 후"에 "재부팅" 옵션 추가

### 수정
- 일부 문자 OCR 인식 이상
- 자동 로그인 감지 이상 [#336](https://github.com/moesnow/March7thAssistant/issues/336)
- 고해상도(High DPI)에서 지원 기능 이상 [#329](https://github.com/moesnow/March7thAssistant/issues/329)
- 고치(적) 줄바꿈 오류 수정 [#328](https://github.com/moesnow/March7thAssistant/issues/328)
- 빛 따라 금 찾아(逐光捡金) 장면 로딩 대기 시간 연장 [#322](https://github.com/moesnow/March7thAssistant/issues/322)
- 장신구 추출 도전 시작 로직 최적화 [#325](https://github.com/moesnow/March7thAssistant/issues/325)
- "실행 실패" 오류 메시지 최적화

## v2.4.0

### 새로운 기능
- 차분화 우주 및 장신구 추출 지원
- "지식의 봉오리•페나코니 대극장" 스테이지 지원
- "운리", "Mar. 7th (허수)", "개척자 (허수)" 지원
- Lark(페이슈) 스크린샷 전송 지원 [#310](https://github.com/moesnow/March7thAssistant/pull/310)

### 수정
- 구버전 재료 합성 페이지 멈춤 문제 [#231](https://github.com/moesnow/March7thAssistant/issues/231)

## v2.3.0

### 새로운 기능
- 시뮬레이션 우주 신규 진입로 적용 (차분화 우주 잠금 해제 필요)
- 2.3 버전 신규 스테이지 지원 [#277](https://github.com/moesnow/March7thAssistant/pull/277)
- B서버 지원 [#269](https://github.com/moesnow/March7thAssistant/pull/269)
- 국제 서버(Global) 계정 작업 지원 [#268](https://github.com/moesnow/March7thAssistant/pull/268)
- 빛 따라 금 찾아 및 지원 캐릭터 "반디" 선택 지원
- 미호요 런처 기본 설치 경로 판단 지원

### 수정
- 도시 샌드박스에 위치할 때 지도 인터페이스 진입 지원
- 혼돈의 기억 갱신 팝업이 실패를 유발할 확률 수정
- PAC 오류 [#276](https://github.com/moesnow/March7thAssistant/pull/276)

## v2.2.0

### 새로운 기능
- 2.2 버전 신규 스테이지 지원
- 빛 따라 금 찾아 및 지원 캐릭터 "어벤츄린" 및 "로빈" 선택 지원
- 설정에서 시뮬레이션 우주 운명의 길 및 난이도 설정 지원 [#223](https://github.com/moesnow/March7thAssistant/pull/223)
- 설정에서 필드 토벌(토벌런) 구매 옵션 설정 지원 [#238](https://github.com/moesnow/March7thAssistant/pull/238)
- 설정 내 다중 계정 관리 기능 추가 [#224](https://github.com/moesnow/March7thAssistant/pull/224)
- 로그인 만료 시 자동 로그인 시도 지원 [#237](https://github.com/moesnow/March7thAssistant/pull/237)
- 템플릿 이미지를 기본적으로 메모리에 캐시 [#244](https://github.com/moesnow/March7thAssistant/pull/244)
- 워프 기록 "비우기" 버튼 추가
- 지원 캐릭터 인터페이스 신규 스타일 적용

### 수정
- "개척자 지원" 및 "의뢰" 인터페이스로 전환 불가 문제 [#247](https://github.com/moesnow/March7thAssistant/pull/247)
- 최신 허구 이야기에서 일부 캐릭터 공격 시작 실패 [#242](https://github.com/moesnow/March7thAssistant/pull/242)
- "지원" 및 "별의 선물" 보상 수령 불가 문제
- 특수 상황에서 워프 기록이 정상 표시되지 않거나 튕기는 문제

## v2.1.1

### 새로운 기능
- 자동 대화 패드(컨트롤러) 인터페이스 지원 [#208](https://github.com/moesnow/March7thAssistant/pull/208)
- Telegram 푸시 방식 프록시 또는 PAC 설정 지원 [#219](https://github.com/moesnow/March7thAssistant/pull/219) [#222](https://github.com/moesnow/March7thAssistant/pull/222)
- 이메일 푸시 방식 Outlook 지원 [#220](https://github.com/moesnow/March7thAssistant/pull/220)

### 수정
- 소스 코드로 필드 토벌 실행 [#211](https://github.com/moesnow/March7thAssistant/pull/211)
- 일부 문자 OCR 인식 이상

## v2.1.0

### 새로운 기능
- 2.1 신규 던전 및 이벤트 지원
- 의뢰 보상 일괄 수령으로 변경
- "고치(적)"을 지역 기반 검색으로 변경
- 출석 체크 이벤트 스위치 통합
- 빛 따라 금 찾아 및 지원 캐릭터 "아케론" 및 "갤러거" 선택 지원

### 수정
- 빨간 점(Red dot)으로 인해 빛 따라 금 찾아이 두 번째 구역 판단 실패
- 합성 임무가 인터페이스 변화로 인해 완료되지 않는 문제
- "고치(적)" 하위 호환성

## v2.0.7

### 새로운 기능
- 사용자 정의 메시지 푸시 형식 지원
- 혼돈의 기억에서 캐릭터 사망 감지 시 자동 재시도
- 일부 실행 로직 최적화
- 전체 실행 종료 후 남은 개척력 및 예상 회복 시간 푸시 (반복 모드 미사용 시) [#197](https://github.com/moesnow/March7thAssistant/pull/197)

### 수정
- 모바일 메뉴 아이콘 클릭 이상

## v2.0.6

### 새로운 기능
- 일일 몰입기 합성 개수 사용자 정의 지원 [#165](https://github.com/moesnow/March7thAssistant/pull/165)
- 로그 빠른 보기 버튼 추가 [#150](https://github.com/moesnow/March7thAssistant/pull/150)
- "전체 실행" 개척력 소모 전 "의뢰 보상 감지" 1회 추가 [#171](https://github.com/moesnow/March7thAssistant/pull/171)

### 수정
- 던전 검색 시 스크롤 속도 감소
- 일부 사용자의 "'cmd'는 내부 또는 외부 명령이 아닙니다..." 오류로 인한 게임 실행 불가 문제
- 일부 해상도에서 전체 화면 상태 판단 이상 [#183](https://github.com/moesnow/March7thAssistant/pull/183)

### 기타
- 홈 화면에서 시뮬레이션 우주 빠른 시작 클릭 시 주간 보상도 수령
- 설정 내 필드 토벌 및 시뮬레이션 우주 업데이트 버튼 제거 (홈 화면에서 해당 기능 실행 권장)

## v2.0.5

### 새로운 기능
- "작업 완료 후"에 "로그아웃" 옵션 추가
- 도구 상자에 프레임 잠금 해제 추가 [#161](https://github.com/moesnow/March7thAssistant/pull/161)
- "해상도 자동 수정 활성화" 옵션을 "해상도 자동 수정 및 자동 HDR 끄기 활성화"로 변경 [#156](https://github.com/moesnow/March7thAssistant/pull/156)
- [OneBot](https://onebot.dev) 푸시 방식(QQ 봇) 추가
- 기업용 위챗 앱 푸시 방식 이미지 전송 지원

### 수정
- 일부 상황에서 프레임 잠금 해제 실패
- 일부 상황에서 Gotify 알림 발송 불가
- 임무 추적 아이콘으로 인한 지도 인터페이스 인식 불가
- 다중 빨간 점으로 인한 시뮬레이션 우주 주간 보상 수령 실패
- 교육 애니메이션 빠른 잠금 해제로 인한 허구 이야기 이상
- 홈 화면 Mar. 7th 배경이 높은 배율에서 흐리게 나오는 문제
- 특정 런처가 해상도 레지스트리 항목을 수정하여 레지스트리 읽기 오류 발생

## v2.0.4

### 새로운 기능
- 워프 기록 내보내기 및 간단 분석 ([SRGF](https://uigf.org/zh/standards/srgf.html) 데이터 형식 가져오기 및 내보내기 지원)
- 빛 따라 금 찾아 및 지원 캐릭터 "스파클" 선택 지원

### 수정
- 특수 상황에서 다운로드 실패

## v2.0.3

### 새로운 기능
- 모든 모바일 배경화면 지원
- "자동 스토리" 명칭을 "자동 대화"로 변경
- 던전 이름에 "없음(건너뛰기)" 옵션 추가
- 1920*1080 이상의 16:9 해상도 지원 (실험적 기능)

### 수정
- 지도 인터페이스 판단 실패
- "해상도 자동 수정" 실패
- "해상도 자동 수정 활성화" 옵션 해제 시 게임 실행 불가 문제

## v2.0.2

### 새로운 기능
- 파티 편성 인터페이스 최적화
- 홈 화면 일부 모듈 다중 옵션 지원 (필드 토벌, 시뮬레이션 우주, 빛 따라 금 찾아)
- 필드 토벌 및 시뮬레이션 우주 설정 파일 초기화 지원
- "게임 갱신 시간", "해상도 자동 수정 활성화", "게임 경로 자동 설정 활성화" 옵션 추가
- 일부 인터페이스 네트워크 재연결 지원

### 수정
- 3D 지도 인터페이스 인식 지원
- 혼돈의 기억 갱신 후 첫 진입 시 신규 팝업 적용

## v2.0.1

### 새로운 기능
- 유물 던전 완료 후 "4성 이하 유물 자동 분해" 기능 추가 (기본값 꺼짐)
- "자동 스토리" 기능 추가 (사이드바 도구 상자 내 활성화)
- "게임 실행" 버튼 추가 (어시스턴트를 런처로 사용 가능)
- 해상도 자동 수정 지원 및 게임 실행 후 원본 해상도 복구 지원
- 사용자 정의 푸시 방식 지원 [#136](https://github.com/moesnow/March7thAssistant/pull/136)

### 수정
- 업데이트 프로그램 덮어쓰기 실패
- 이상 상태에서 전쟁의 여운 3회 미완료 문제
- 경로에 공백이 포함된 경우 업데이트 시 브라우저로 이동하는 문제
- 업데이트 프로그램이 Fhoe-Rail\map 디렉터리를 잘못 삭제하는 문제 (이 문제 발생 시 수동으로 개별 업데이트 클릭 필요)

## v2.0.0

### 새로운 기능
- 2.0 버전 신규 스테이지 지원
- "한정 조기 해금" 스테이지 지원
- "고치(금) 선호 지역" 선택 지원
- 망각의 정원 및 지원 캐릭터 "Dr. 레이시오", "블랙 스완", "미샤" 선택 지원

### 수정
- 일부 기기에서 "타오르는 형상" 스테이지 OCR 인식 이상
- "고치(적)" 임계값 요구 사항 완화
- "「만능 합성기」 1회 사용" 합성 재료를 "미광 원핵"으로 변경
- 버전 업데이트 후 "기억" 전환 이상
- 버전 업데이트 후 "빛 따라 금 찾아" 전환 이상
- 출석 체크 이벤트 이미지 읽기 실패

## v1.7.7

### 새로운 기능
- SMTP 스크린샷 전송 지원 [#114](https://github.com/moesnow/March7thAssistant/pull/114)
- Gotify 푸시 방식 지원 [#112](https://github.com/moesnow/March7thAssistant/pull/112)
- "지원 캐릭터 사용 활성화" 옵션 추가 (기본값 켜짐) [#121](https://github.com/moesnow/March7thAssistant/issues/121)
- "지정 친구의 지원 캐릭터" 설명 수정 (사용자 이름과 UID 모두 지원)

### 수정
- 원격 데스크톱 다중 실행 시 다른 사용자의 게임 프로세스를 잘못 종료하는 문제 [#113](https://github.com/moesnow/March7thAssistant/pull/113) [#35](https://github.com/moesnow/March7thAssistant/issues/35)
- 일부 문자 OCR 인식 이상 (예: RapidOCR의 고치 관련 문제)
- 경로에 영문 괄호가 포함된 경우 압축 해제 실패
- 시뮬레이션 우주 완료 후 보상 수령 불가 문제

## v1.7.6

### 새로운 기능
- 이벤트 꽃이 피는 정원, 기묘한 영역, 차원 분열 지원 (기본값 꺼짐)

## v1.7.5

### 새로운 기능
- 허구 이야기 지원 (기본 스테이지 범위 3-4)

## v1.7.4

### 새로운 기능
- 업데이트 시 전체 패키지 다운로드 지원 (기본값 켜짐, 설정→정보)
- 미리보기(Preview) 버전 업데이트 채널 가입 지원 (설정→정보)
- 업데이트 시 aria2를 호출하여 멀티스레드 다운로드 지원 (속도 향상 및 다운로드 중단 감소)
- 업데이트 시 더 이상 시스템 임시 디렉터리를 사용하지 않음 (백신 화이트리스트 추가 용이 [#86](https://github.com/moesnow/March7thAssistant/discussions/86#discussioncomment-7966897))

### 수정
- 반복 도전 던전 실행 이상

## v1.7.3

### 새로운 기능
- 망각의 정원 및 지원 캐릭터 "아젠티" 선택 지원
- "자동 전투 감지 활성화" 끄기 지원 (설정→키)
- "자동 전투 감지" 시간을 무제한으로 변경 (임시 수정 [#96](https://github.com/moesnow/March7thAssistant/pull/96))

### 수정
- 망각의 정원 파티 교체 후 비술 사용 순서 미교체
- 망각의 정원 도전 실패 후 다음 층 도전 시도

## v1.7.2

### 새로운 기능
- 일일 훈련 끄기 지원 (매일 시뮬레이션 우주 1회로 활약도 500 달성 가능)
- 신규 전쟁의 여운 「별을 갉아먹는 옛 정원」 지원
- 망각의 정원 및 지원 캐릭터 "완·매" 선택 지원

### 수정
- 망각의 정원 전송 시 드물게 신용 포인트 아이콘을 잘못 클릭하는 문제 [#91](https://github.com/moesnow/March7thAssistant/pull/91)

## v1.7.1


### 수정
- 필드 토벌 및 시뮬레이션 우주 실행 이상

## v1.7.0

### 새로운 기능
- 일일 훈련 신규 임무 적용
- 혼돈의 기억 신규 인터페이스 적용 (7층 최초 클리어 후 수동으로 교육 애니메이션 완료 필요)
- 혼돈의 기억 캐릭터 선택 화면 스크롤 검색 지원
- 혼돈의 기억 도전 실패 후 자동 파티 교체
- 혼돈의 기억 기본 스테이지 범위 7-12로 변경
- 지원되는 파티 번호 3-7로 변경
- 망각의 정원 및 지원 캐릭터 "한아" 및 "설의" 선택 지원
- 딩톡(Dingtalk) 푸시 기본 설정에 secret 파라미터 추가

### 수정
- 혼돈의 기억 완료 후 보상 수령 실패

## v1.6.9

### 새로운 기능
- 혼돈의 기억 1-5층 단일 보스 변경 적용

### 수정
- 스크롤 후 지연 부족으로 일부 인터페이스 인식 위치 이탈 (다시 발생)
- 일부 테스트 코드 제거

## v1.6.8


### 수정
- 시뮬레이션 우주 실행 빈도 설정 이름 오류

## v1.6.7

### 새로운 기능
- 개척력으로 몰입기 우선 합성 지원 (기본값 꺼짐)
- 시뮬레이션 우주 실행 빈도 수정 지원 (기본값 매주 1회)

### 수정
- 스크롤 후 지연 부족으로 일부 인터페이스 인식 위치 이탈

## v1.6.6

### 새로운 기능
- "일일 훈련" 및 "개척력 소모" 작업 개별 실행 지원
- Fhoe-Rail 업데이트 전 구버전 map 폴더 자동 삭제

### 수정
- 라인업 자동 저장으로 인한 "기억" 및 "혼돈의 기억" 실행 불가
- 일부 생소한 글자가 포함된 던전 이름 인식 실패 확률 감소

## v1.6.5

### 새로운 기능
- 통합 모드로 시뮬레이션 우주 실행 지원 (기본값)
- 망각의 정원 및 지원 캐릭터 "토파즈&복순이", "계네빈", "곽향" 선택 지원
- 던전 "유부의 형상" 및 "유명의 길" 추가
- 고치 개척력 60 미만 상황 지원 [#31](https://github.com/moesnow/March7thAssistant/pull/31)
- "시작 메뉴" 바로가기에서 게임 경로 획득 지원 [#29](https://github.com/moesnow/March7thAssistant/pull/29)

### 수정
- 런처에서 게임 경로 자동 획득 수정
- "소모품 사용" 선택 실패 후 재시도 로직 오류 [#41](https://github.com/moesnow/March7thAssistant/pull/41)

## v1.6.4

### 새로운 기능
- 시뮬레이션 우주 매주 실행 횟수 사용자 정의 지원
- "「시뮬레이션 우주」(임의의 세계) 1개 구역 통과" 완료 지원
- 시뮬레이션 우주 무결성 검사 추가 [#27](https://github.com/moesnow/March7thAssistant/pull/27)
- "개척자(남)•파멸" 및 "개척자(남)•보존" 지원 [#26](https://github.com/moesnow/March7thAssistant/pull/26)

### 수정
- "게임 종료 실패" 문제 수정 (실험적 변경 사항 롤백)

## v1.6.3

### 새로운 기능
- "히메코 체험"을 통한 일부 일일 훈련 완료 지원 (실험적)
- "기억 1"을 통한 일부 일일 훈련 완료 지원 (실험적)
- Python 3.12.0 기반 구동
- Fhoe-Rail 최신 변경 사항 적용

### 수정
- "타임아웃 시간"을 소수로 수정 시 그래픽 인터페이스 충돌
- 별의 선물 및 7일 출석 마지막 날 보상 수령 불가
### 기타
- 기존 기능 안정성 최적화
- 이제 현재 사용자의 게임 프로세스만 중지 (실험적)

## v1.6.2

### 새로운 기능
- "예비 개척력" 및 "연료" 사용 지원
- 이벤트 "별의 선물" 보상 수령 지원
- go-cqhttp 스크린샷 전송 지원 [#21](https://github.com/moesnow/March7thAssistant/pull/21)

### 수정
- 개척력을 "미" 글자로 인식할 확률 감소
### 기타
- power_total, dispatch_count, ocr_path 설정 항목 제거
- 소모품 사용 전 가방 아이템 과다 방지를 위해 카테고리 우선 필터링
- [PaddleOCR-json_v.1.3.1](https://github.com/hiroi-sora/PaddleOCR-json/releases/tag/v1.3.1) 업그레이드, Win7 x64 호환
- [RapidOCR-json_v0.2.0](https://github.com/hiroi-sora/RapidOCR-json/releases/download/v0.2.0/RapidOCR-json_v0.2.0.7z) 지원, AVX 명령어 집합 미지원 CPU 호환 (자동 판단)

## v1.6.1

### 새로운 기능
- "던전 이름" 프리셋 (설명 포함)
- "경류" 및 "개척자(여)•파멸" 지원
- 이벤트 "별의 선물" 보상 수령 지원
- "무명의 공훈 열기" 인터페이스 인식 지원

### 수정
- PushPlus 푸시 [#14](https://github.com/moesnow/March7thAssistant/pull/14)
### 기타
- 모바일 배경화면 상태 판단 지원
- "무명객의 영광" 구매 여부 판단 지원
- 파티 설정 방식을 키 입력 대신 모바일 화면 진입으로 변경

## v1.6.0

### 새로운 기능
- 혼돈의 기억 완료 후 성옥 보상 자동 수령
- 통합 모드로 필드 토벌 실행 지원 (기본값)
- 그래픽 인터페이스 테스트 메시지 푸시 기능 추가
- 대부분의 푸시 방식에 필요한 설정 항목 보완 (Bark, ServerChan, 이메일 SMTP 추천)
- 공식 런처에서 게임 경로 획득 지원 [#10](https://github.com/moesnow/March7thAssistant/pull/10)

### 수정
- Windows 터미널 상위 버전 "오류 2147942402 (0x80070002)" 팁 [#12](https://github.com/moesnow/March7thAssistant/pull/12)
- 저사양 PC에서 의뢰 상태 감지 간헐적 이상
- "오류 발생: None" 오류 메시지 최적화
- 시스템 설정 "강조 색 표시" 켜기 시 그래픽 인터페이스 표시 이상 [#11](https://github.com/moesnow/March7thAssistant/pull/11)
### 기타
- 멀티스레딩 사용하여 그래픽 인터페이스 로딩 시간 대폭 단축 [#11](https://github.com/moesnow/March7thAssistant/pull/11)
- Python 버전 감지 및 의존성 설치 최적화
- "사용 튜토리얼" 내장 (웹 버전 권장)

## v1.5.0

### 새로운 기능
- 그래픽 인터페이스의 "던전 이름", "오늘의 훈련" 표시 방식 최적화
- 국제 서버(Global) 런처 인터페이스 지원 시도 (간체 중문)
- "게임 종료", "자동 종료" 등 기능을 "작업 완료 후"로 통합, 기본값 "없음"
- 반복 실행 4시 시작 시 0-10분 무작위 지연 실행

### 수정
- 업데이트 시 그래픽 인터페이스 자동 종료 안 됨 (파일 점유로 인한 업데이트 실패)
- 작업 디렉터리가 올바르지 않아 실행 불가 (작업 스케줄러 사용 시 흔함)
### 기타
- 가장 빠른 미러 소스 자동 속도 측정 및 선택
- 이제 "타임아웃" 기능이 "필드 토벌", "시뮬레이션 우주" 하위 작업을 올바르게 강제 중지
- conhost 대신 Windows Terminal 우선 사용
- "python_path", "pip_mirror", "github_mirror" 등 설정 항목 폐기

## v1.4.2

### 새로운 기능
- [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 자동 필드 토벌 프로젝트 내장, 설정 인터페이스에서 개별 업데이트 지원 (제작자에게 Star 부탁드려요)
- 디렉터리 구조 조정, 수동 업데이트 권장 (자동 업데이트는 미사용 파일을 삭제하지 않음)

## v1.4.1.1


### 수정
- 간헐적으로 월정액 수령 불가
- 환경 변수에서 Python 경로 자동 획득 실패
- pushplus 푸시 문제 (다시 발생)

## v1.4.1

### 새로운 기능
- 망각의 정원 및 지원 캐릭터 "부현" 및 "링스" 선택 지원
- 훈련 "「망각의 정원」 1회 완료" 스위치 옵션 추가 (기본값 꺼짐)
- 작업 완료 후 소리 알림 재생 지원 (기본값 꺼짐)
- Windows 기본 알림 지원 (기본값 켜짐)
- 일부 오류 메시지 최적화

### 수정
- 필드 토벌 원본 실행 오류
- pushplus 푸시 문제

## v1.4.0

### 새로운 기능
- 작업 완료 후 자동 종료(Shutdown) 지원 (기본값 꺼짐)
- 그래픽 인터페이스 탐색 바 최적화
- 그래픽 인터페이스 다크 모드 지원

### 수정
- 던전 전송 클릭 후 대기 시간 연장

## v1.3.5

### 새로운 기능
- 그래픽 인터페이스에서 비술 키 수정 지원 [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- 그래픽 인터페이스에서 설정 파일 가져오기 지원 [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- 지정 친구의 지원 캐릭터 사용 지원 [#5](https://github.com/moesnow/March7thAssistant/pull/5)
- 다운로드 과정 진행률 표시 지원

### 수정
- 모바일 배경화면 변경 시 의뢰 감지 실패

## v1.3.4.2

### 새로운 기능
- 설정 파일에 비술 키 수정 추가 [#3](https://github.com/moesnow/March7thAssistant/pull/3)

### 수정
- 차원 분열 이벤트 배너로 인해 헤르타 사무실 자동 진입 불가
- 그래픽 인터페이스에서 "던전 필요 개척력" 설정 항목 숨김 (오수정 방지)
- 일일 임무 "「망각의 정원」 1회 완료"에서 멈추는 문제 해결 시도
- 자동 전투가 자동 켜지지 않는 문제 해결 시도

## v1.3.4.1


### 수정
- powershell 명령을 cmd 실행으로 수정
- Python 자동 설치 관련 일부 문제 수정 (실험적)

## v1.3.4

### 새로운 기능
- 망각의 정원 및 지원 캐릭터 "단항•음월" 선택 지원
- 설정에서 시뮬레이션 우주 및 필드 토벌 원본 그래픽 인터페이스 열기 지원 (운명의 길 설정 등 용도)
- Python, PaddleOCR-json 자동 다운로드 및 설치 지원 (실험적)
- March7thAssistant 및 시뮬레이션 우주 업데이트 기능 최적화 (실험적)

### 수정
- 비 4K 해상도 창 모드 실행 시 기능 이상

## v1.3.3.1

### 새로운 기능
- 게임 시작 후 게임 경로 자동 감지 및 저장 지원
- 자주 묻는 질문(FAQ) 업데이트

## v1.3.3

### 새로운 기능
- 무명의 공훈 보상 수령 여부 설정 지원 (기본값 꺼짐)
- 더 많은 오류 감지 추가
- 자주 묻는 질문(FAQ) 업데이트

## v1.3.2

### 새로운 기능
- "자동 전투" 자동 켜기 지원
- 필드 토벌 및 시뮬레이션 우주 실행 상태 인식 지원
- 게임 업데이트로 인한 재부팅 필요 인식 지원
- 공식 런처가 열려 있는 상태에서 게임 실행 지원
- 필드 토벌 및 시뮬레이션 우주 스크립트 오류 발생 시 즉시 종료

### 수정
- 작업 실행 후 그래픽 인터페이스가 닫히지 않은 상태에서 설정 수정 시 시간 및 일일 상태가 덮어씌워지는 문제
- 게임 시작 후 메인 화면이 아닐 때 시작 실패 판정 (이제 알려진 임의의 화면 지원)

## v1.3.1

### 새로운 기능
- 시뮬레이션 우주 "몰입 보상 수령" 지원, 설정에서 켜기 (기본값 꺼짐)
- 시뮬레이션 우주 버전 개별 업데이트 지원 (실험적)
- 그래픽 인터페이스 버전 자동 업데이트 지원 (실험적)
- 그래픽 인터페이스 수동 업데이트 확인 지원
- 그래픽 인터페이스 "업데이트 내역", "자주 묻는 질문" 등 하위 페이지 추가

### 수정
- 시뮬레이션 우주 완료 후 알림 스크린샷 최적화

## v1.3.0.2

### 새로운 기능
- v1.3.0에서 제거된 지원 캐릭터 사용(borrow_character_enable) 옵션 복구
- 던전 이름을 "없음"으로 설정 시 해당 훈련 임무가 있어도 수행하지 않음

## v1.3.0.1


### 수정
- v1.3.0 그래픽 인터페이스를 통해 생성된 설정 파일이 올바르지 않음

## v1.3.0

### 새로운 기능
- 일일 훈련 내용을 인식하고 전부 수행하는 대신 시도하여 완료 지원 [지원 임무 보기](https://github.com/moesnow/March7thAssistant#%E6%AF%8F%E6%97%A5%E5%AE%9E%E8%AE%AD)
- 매주 「전쟁의 여운」 3회 우선 완료 옵션 추가 (기본값 꺼짐)
- 던전 이름(instance_names)을 던전 유형별 개별 설정으로 변경, "xxx 1회 완료" 실전 임무에도 사용됨
- "지원 캐릭터 사용", "강제 지원 캐릭터 사용", "일일 사진 촬영 활성화", "일일 재료/소모품 합성/사용 활성화" 설정 옵션 제거
- 매주 시뮬레이션 우주 실행 전 수령 가능한 보상 우선 확인

### 수정
- 낮은 확률로 던전 이름 인식 실패 문제 해결 시도
- 일일 훈련 전체 완료 감지 신뢰 불가 문제 완전 해결

## v1.2.6

### 새로운 기능
- 더 많은 던전 유형 지원: 침식된 터널, 정체된 허영, 고치(금), 고치(적)
- 설정의 스크린샷 캡처 기능 OCR 문자 인식 지원 (던전 이름 복사 용도)

## v1.2.5

### 새로운 기능
- 필드 토벌 명령 내장


### 수정
- 개척력을 "/240" 대신 "1240"으로 인식하는 문제
- 일일 훈련 전체 완료 감지 실패

## v1.2.4

### 새로운 기능
- 그래픽 인터페이스 업데이트 내역 표시 지원
- 시뮬레이션 우주 [Auto_Simulated_Universe  v5.30](https://github.com/CHNZYX/Auto_Simulated_Universe/tree/f17c5db33a42d7f6e6204cb3e6e83ec2fd208e5e) 업데이트


### 수정
- 1.3 버전의 각종 UI 변화로 인한 이상

## v1.2.3

### 새로운 기능
- 혼돈의 기억 매 층 별(Star) 개수 감지 지원
- 던전 이름 약어 지원 (예: 【지혜의 길】)


### 수정
- 간헐적 클릭 속도 과다로 인한 훈련 보상 수령 실패
- 마우스가 화면 좌측 상단에 위치하여 보안 정책 트리거로 인한 클릭 실패
- 간헐적 인터페이스 전환 속도 지연으로 인한 소모품 인식 클릭 위치 이탈
- 무명의 공훈 보상 템플릿 이미지 오류 감지
- 일부 임계값 요구 사항 완화, 작업 성공률 향상
- 일부 불필요한 인터페이스 감지 제거, 속도 향상

## v1.2.2

### Features
- feat: add Bailu and Kafka
백로 및 카프카 적용
- feat: forgottenhall support melee character
혼돈의 기억 근접 캐릭터 공격 시작 지원
- feat: add take_screenshot to gui
그래픽 인터페이스 설정에 스크린샷 캡처 기능 추가
- feat: add check update to gui
그래픽 인터페이스 시작 시 업데이트 확인
- feat: add tip when start

### Fixes
- fix: use consumables when repeat
소모품 효과 미만료로 인한 사용 불가 수정
- fix: check_update option not available
업데이트 확인 스위치 사용 불가 수정
- fix: avoid trailblaze_power overflow
시뮬레이션 우주 전후 개척력 1회 소모하여 넘침 방지
- fix: space cause text ocr fail
간헐적으로 공백 인식으로 인한 문자 판단 실패 수정
- fix: exit function

## v1.2.1

### Features
- feat: auto change team
던전 및 필드 토벌 전 자동 파티 교체 가능
- feat: add submodule Auto_Simulated_Universe
시뮬레이션 우주 서브 모듈 추가

### Fixes
- fix: switch window problem
게임 창이 간헐적으로 전경으로 전환되지 않는 문제
- fix: same borrow character
지원 캐릭터와 원본 파티 캐릭터가 동일한 문제

## v1.2.0

### Features
- feat: graphical user interface
그래픽 사용자 인터페이스(GUI) 추가