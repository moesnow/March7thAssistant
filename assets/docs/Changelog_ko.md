# 업데이트 로그

## v2026.1.21
- 화폐 전쟁 포인트 보상 수령 후 심연의 몰입기 자동 사용 지원
- MeoW 푸시 알림 지원 추가 [#850](https://github.com/moesnow/March7thAssistant/pull/850) @pboymt
- 성능 및 안정성 최적화, 알려진 문제 수정
- 주의: v2026.1.18 업데이트에 버그가 있으므로, [수동 다운로드](https://github.com/moesnow/March7thAssistant/releases/tag/v2026.1.21)하여 덮어쓰기 업데이트가 필요합니다!!!
- [Mirror 짱 CDK가 있다면 여기를 클릭하여 고속 다운로드](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-release)

## v2026.1.19
- 그래픽 인터페이스 전면 업그레이드 및 최적화
- 게임 시작 전 전투 2배속 자동 감지 및 켜기 기능 추가
- 소스 코드 실행 시 macOS/Linux 지원 및 [Docker 배포](https://m7a.top/#/assets/docs/Docker) 지원
- 트레이 아이콘 우클릭 메뉴에 설정 옵션 추가
- 클라우드 게임 창 없는 모드에서 QR 코드 로그인 지원
- 클라우드 게임 대기열에 예상 대기 시간 표시 추가
- OCR 추론 엔진 및 모델 업그레이드
- "실행 파일을 찾을 수 없습니다" 오류 메시지 최적화 [해결 방법](https://m7a.top/#/assets/docs/FAQ)
- 자원이 충분하지 않을 때 육성 계획이 장신구 추출을 실행하던 문제 수정
- 일부 텍스트 OCR 인식 이상 수정
- 트레이에서 복귀 시 로그 창이 비정상적으로 비어 보이던 문제 수정
- QR 코드 만료 후 제대로 새로고침되지 않던 문제 수정 [#843](https://github.com/moesnow/March7thAssistant/pull/843) @eloay

## v2025.12.31
- HoYoPlay 런처를 통한 게임 자동 업데이트 지원 ("설정 → 프로그램"에서 활성화)
- 예약 작업에 런처를 통한 게임 사전 다운로드 추가 지원
- 이제 동일한 경로에서는 하나의 그래픽 인터페이스 인스턴스만 실행됩니다
- 더 많은 텍스트 OCR 인식 이상 수정 [#828](https://github.com/moesnow/March7thAssistant/pull/828) @loader3229
- 클라우드 게임이 대기열을 선택하지 않던 문제 수정 [#830](https://github.com/moesnow/March7thAssistant/pull/830) @loader3229
- 프로그램 창을 전경으로 전환할 때 가끔 실패하던 문제 수정
- 테마 변경 후 트레이에서 복귀 시 인터페이스를 다시 로드해야 했던 문제 수정

## v2025.12.26
- 예약 실행에 다중 예약 작업 및 외부 프로그램 추가 지원
- 리딤코드를 하나도 찾지 못했을 때의 처리 로직 최적화
- 클라우드 게임 설정의 최대 대기 허용 시간 범위 조정
- Bilibili 서버 로그인 화면 UI 변경으로 인한 시작 오류 수정
- 일부 상황에서 일일 훈련 보상 수령을 미완료로 오판하던 문제 수정 [#820](https://github.com/moesnow/March7thAssistant/pull/820) @g60cBQ
- 던전을 인식하지 못했을 때 육성 목표가 계속 실행되던 문제 수정 [#819](https://github.com/moesnow/March7thAssistant/pull/819) @g60cBQ

## v2025.12.21
- 다알리아 및 Mar. 7th·겨울과 작별 지원 [#813](https://github.com/moesnow/March7thAssistant/pull/813) @loader3229
- 업적 보상 수령 기능 추가 [#811](https://github.com/moesnow/March7thAssistant/pull/811) @g60cBQ
- 리딤코드 자동 획득 및 수령 기능 추가
- 터치스크린 모드 지원 복구
- 예약 실행 작업의 트리거 로직 최적화
- 화폐 전쟁 미결산 대국 처리 최적화
- 풀 버전 패키지에 클라우드 게임 전용 브라우저 내장 [#815](https://github.com/moesnow/March7thAssistant/pull/815) @Patrick16262
- 복귀 유저의 이벤트 페이지 인식 문제 수정
- 특정 상황에서 개척력 계획이 실행 불가로 잘못 판단되던 문제 수정
- 육성 계획 활성화 시 던전 연속 도전 횟수 오류 수정
- 클라우드·붕괴: 스타레일 백그라운드 실행 시 클립보드 오작동 문제 수정 [#816](https://github.com/moesnow/March7thAssistant/pull/816) @Patrick16262
- 클라우드 게임 사용 시 필드 정리를 빠르게 시작할 수 없던 문제 수정

## v2025.12.16
- 로그 인터페이스 추가 및 작업 실행 방식 최적화
- 그래픽 인터페이스 터치 스크롤 지원 추가 [#799](https://github.com/moesnow/March7thAssistant/pull/799) @g60cBQ
- 그래픽 인터페이스 트레이로 최소화 지원
- 클라우드 게임 다운로드 시 국내 미러 소스 사용하여 가속 [#792](https://github.com/moesnow/March7thAssistant/pull/792) @Patrick16262
- 클라우드 게임 관련 여러 문제 최적화 및 수정 [#800](https://github.com/moesnow/March7thAssistant/pull/800) [#804](https://github.com/moesnow/March7thAssistant/pull/804) @Patrick16262
- WebHook 푸시 알림에 더 많은 설정 옵션 지원
- 자동 테마 기능이 정상 작동하지 않던 문제 수정
- 차분 우주 포인트 보상 실행 시 분류 선택 오류 수정
- 언어가 중국어가 아닐 때 로그 인터페이스 표시 이상 수정

## v2025.12.13

- 개척력 계획 지원
- 설정 인터페이스 최적화
- 2배 이벤트에서 육성 계획 읽기 지원 [#751](https://github.com/moesnow/March7thAssistant/pull/751) @g60cBQ
- 이제 일일 훈련 완료 판단 시 즉시 보상을 수령합니다
- 장신구 추출 시 캐릭터 미설정 시 자동으로 첫 번째 파티 선택 [#788](https://github.com/moesnow/March7thAssistant/pull/788) @g60cBQ
- 프레임 잠금 해제 및 해상도 자동 변경 기능 글로벌 서버 지원
- 설정 파일 변경 시 그래픽 인터페이스 자동 리로드

## v2025.12.10

- 화폐 전쟁 관련 여러 문제 최적화 및 수정
- 던전 이름 및 파티 캐릭터 수동 입력 및 실시간 자동완성 지원
- 알림 레벨 설정 지원 (예: 오류 알림만 푸시)
- 푸시 알림 전 스크린샷 압축하여 용량 감소
- KOOK, WebHook 푸시 알림 지원 추가
- Bark 푸시 암호화 지원 추가
- 30일이 지난 로그 파일 자동 정리 기능 추가

## v2025.12.8

- 화폐 전쟁 지원
- 화폐 전쟁 관련 여러 이상 문제 수정
- 뽑기 기록 UIGF 형식 가져오기 및 내보내기 지원
- 개척력 소모 전 임의의 앵커로 텔레포트 [#760](https://github.com/moesnow/March7thAssistant/pull/760) @Xuan-cc
- 클라우드 게임 관련 여러 문제 최적화 및 수정 [#763](https://github.com/moesnow/March7thAssistant/pull/763) @Patrick16262
- 임무 완료 후 모니터 끄기 지원 추가
- 뽑기 기록 비우기 시 재확인 팝업 추가
- 육성 목표에서 고치 던전 정보 추출 실패 수정 [#764](https://github.com/moesnow/March7thAssistant/pull/764) @g60cBQ
- 임무 완료 후 ps1 스크립트 실행 실패 수정 [#759](https://github.com/moesnow/March7thAssistant/pull/759) @0frostmourne0

## v2025.12.1

- 클라우드·붕괴: 스타레일 지원 [#750](https://github.com/moesnow/March7thAssistant/pull/750)
- 육성 목표에 따른 동적 던전 선택 지원 [#751](https://github.com/moesnow/March7thAssistant/pull/751)
- 일일 훈련이 이제 임무 완료 상태를 읽고 작업 실행을 조정합니다 [#753](https://github.com/moesnow/March7thAssistant/pull/753)
- 기업용 위챗 봇 푸시 방식 이미지 전송 지원 [#742](https://github.com/moesnow/March7thAssistant/pull/742)
- 특정 상황에서 상시 도전 캐릭터 선택 오류 수정 [#747](https://github.com/moesnow/March7thAssistant/pull/747)
- 임무 완료 후 스크립트 선택 시 튕김 현상 수정
- 가끔 게임 프로세스를 정상적으로 종료하지 못하던 문제 수정
- UI 변경으로 인한 차분 우주 및 시뮬레이션 우주 자동 전투 감지 이상 수정
- 전체 실행 시 임무 순서 최적화
- 업데이트 프로그램의 일부 문제 최적화
- 자동 로그인 흐름 최적화

## v2025.11.11

- "차분 우주 1회 우선 실행" 주기를 격주 1회로 업데이트
- SMTP 알림 전송 시 사용자 이름 미사용 지원 [#730](https://github.com/moesnow/March7thAssistant/pull/730) [#738](https://github.com/moesnow/March7thAssistant/pull/738)
- 3.7 신규 주간 보스 인식 이상 수정 [#728](https://github.com/moesnow/March7thAssistant/pull/728)
- 리딤코드 입력창 인식 이상 수정 [#734](https://github.com/moesnow/March7thAssistant/pull/734)
- 특정 조건에서 지원 캐릭터 선택 화면 클릭 이상 수정

## v2025.11.6

- 3.7 버전 신규 스테이지 및 캐릭터 지원 [#725](https://github.com/moesnow/March7thAssistant/pull/725)
- 일부 던전 유형 연속 도전 지원 추가
- 자동 대화 도구 리팩토링: 설정 옵션 추가 및 문제 수정 [#720](https://github.com/moesnow/March7thAssistant/pull/720)
- 자주 묻는 질문에 다중 모니터 관련 문제 및 해결 방법 추가
- 다중 계정 로그인 화면 멈춤 문제 수정 [#723](https://github.com/moesnow/March7thAssistant/pull/723)
- 시뮬레이션 우주 진입 UI 변경으로 인한 이상 수정
- 이벤트 화면 UI 변경으로 인한 이상 수정
- 차분 우주 지원 UI 변경으로 인한 이상 수정
- 설정 화면의 전쟁의 여운 실행 요일 표시 오류 수정
- 그래픽 인터페이스 레이아웃 최적화

## v2025.10.15

- 3.6 버전 신규 캐릭터 지원
- 자동 로그인 과정 최적화 및 글로벌 서버 호환성 향상 [#706](https://github.com/moesnow/March7thAssistant/pull/706)
- 파티 내 캐릭터 사망 시 던전 계속 도전 지원 [#705](https://github.com/moesnow/March7thAssistant/pull/705)
- HDD 사용자를 위해 일부 타임아웃 시간 연장 [#701](https://github.com/moesnow/March7thAssistant/pull/701)
- "성공 후 프로그램 일시정지" 및 "실패 후 즉시 종료" 옵션 추가 [#704](https://github.com/moesnow/March7thAssistant/pull/704) [#709](https://github.com/moesnow/March7thAssistant/pull/709)
- 일부 사용자의 다운로드 이상 문제 수정
- 다운로드 프로그램 시스템 프록시 자동 사용 최적화
- 설정 파일 초기화 기능의 오류 메시지 최적화

## v2025.9.25

- 3.6 버전 신규 스테이지 및 캐릭터 지원
- 일일 "재료 합성" 프로세스 최적화 및 설정에서 끄기 지원
- "지원 목록" 친구 이름 공란 지원 (선택한 캐릭터만 검색)
- 지원 캐릭터 "선데이" 설정 후 친구 이름 인식 이상 문제 수정
- "뽑기 기록" 데이터 업데이트 시 튕김 현상 수정
- "사용자 로그인 시 시작" 옵션 설명 최적화
- 여러 던전 이름 인식 오류 수정

## v2025.9.10

- 3.5 버전 신규 스테이지 및 캐릭터 지원 [#687](https://github.com/moesnow/March7thAssistant/pull/687)
- 여러 던전 이름 인식 오류 수정
- 이메일 인식 이상 수정

## v2025.8.13

- 3.5 버전 신규 스테이지 및 캐릭터 지원 [#671](https://github.com/moesnow/March7thAssistant/pull/671)
- 여러 던전 이름 인식 오류 수정

## v2025.7.20

- Fate 콜라보 캐릭터 지원 [#640](https://github.com/moesnow/March7thAssistant/pull/640)
- 뽑기 기록 콜라보 워프 지원
- 지도 및 워프 단축키 수정 지원 추가 [#635](https://github.com/moesnow/March7thAssistant/pull/635)
- "자동 대화" 기능 "대화 자동 건너뛰기" 지원 [#639](https://github.com/moesnow/March7thAssistant/pull/639)
- 다중 계정 관리 기능 레지스트리 정리 지원 [#636](https://github.com/moesnow/March7thAssistant/pull/636)
- 차원 분열 이벤트로 인한 오류 수정 [#643](https://github.com/moesnow/March7thAssistant/pull/643)
- 시뮬레이션 우주 종료 시 발생하는 오류 수정
- 자동 대화가 선택지를 지원하지 않던 문제 수정

## v2025.7.8

- 3.4 버전 신규 스테이지 및 캐릭터 지원 [#616](https://github.com/moesnow/March7thAssistant/pull/616)
- "명족의 형체" 던전 진입 불가 문제 수정

## v2025.6.14

- 3.3 버전 신규 스테이지 및 캐릭터 지원 [#580](https://github.com/moesnow/March7thAssistant/pull/580) [#597](https://github.com/moesnow/March7thAssistant/pull/597)
- 뽑기 기록 Excel 파일 내보내기 지원 [#574](https://github.com/moesnow/March7thAssistant/pull/574)
- 고치 도전 횟수 수정 지원 [#592](https://github.com/moesnow/March7thAssistant/pull/592)
- 설정 페이지 슬라이더에 버튼 추가하여 정밀 제어 지원 [#591](https://github.com/moesnow/March7thAssistant/pull/591)
- 차분 우주 일시정지 이미지 수정 [#594](https://github.com/moesnow/March7thAssistant/pull/594)
- 뽑기 데이터 이상 시 Excel 정상 내보내기 불가 문제 수정
- 일부 옵션 사용 시 그래픽 인터페이스 튕김 문제 수정
- Gotify 푸시 이상 수정
- 시뮬레이션 우주 (Auto_Simulated_Universe) v8.04
- 시뮬레이션 우주 Mirror 짱을 통한 업데이트 지원

## v2025.4.18

- 2주년 이벤트 아이콘 대응
- 카스토르 지원 [#548](https://github.com/moesnow/March7thAssistant/pull/548)
- 전쟁의 여운(주간 보스) 실행 요일 설정 지원 [#479](https://github.com/moesnow/March7thAssistant/pull/479)
- 유물 수량 상한 도달 시 4성 유물 분해 우선 실행 [#524](https://github.com/moesnow/March7thAssistant/pull/524)
- OneBot 개인 메시지와 그룹 메시지 동시 전송 지원 [#540](https://github.com/moesnow/March7thAssistant/pull/540)
- 필드 정리에 온파로스 우선순위 설정 항목 추가 [#547](https://github.com/moesnow/March7thAssistant/pull/547)
- Mirror 짱 사용 경험 최적화, CDK 만료 등 오류 메시지 추가
- Feishu, Gotify, OneBot 푸시 수정 [#520](https://github.com/moesnow/March7thAssistant/pull/520) [#517](https://github.com/moesnow/March7thAssistant/pull/517)
- 일일 훈련 미완료 시 보상 수령이 올바르지 않던 문제 수정
- 시스템이 자동 테마를 지원하지 않을 때 튕기는 문제 수정 [#525](https://github.com/moesnow/March7thAssistant/pull/525)
- 예약 실행 시간이 로컬 지역 설정을 읽을 때 발생하는 튕김 수정 [#512](https://github.com/moesnow/March7thAssistant/pull/512)

## v2025.3.7

- 시뮬레이션 우주(Auto_Simulated_Universe) 신규 버전 차분 우주 대응
- 3.1 버전 신규 스테이지 및 캐릭터 지원 [#486](https://github.com/moesnow/March7thAssistant/pull/486)
- 임무 완료 후 지정 프로그램 또는 스크립트 실행 지원 [#453](https://github.com/moesnow/March7thAssistant/pull/453)
- 매주 1회 차분 우주 우선 실행 지원 (설정-우주)
- Mirror 짱 서드파티 앱 배포 플랫폼 연동 (정보 → 업데이트 소스)
- 육성 목표 설정 후 일부 던전 이상 수정
- 클래식 시뮬레이션 우주 진입 불가 수정
- 소모품 합성 불가 수정 [#482](https://github.com/moesnow/March7thAssistant/issues/482)
- 터치스크린 모드 일시 사용 불가 [#487](https://github.com/moesnow/March7thAssistant/issues/487)

## v2025.1.20

- 3.0 버전 신규 스테이지 및 캐릭터 지원 [#442](https://github.com/moesnow/March7thAssistant/pull/442)
- "Matrix" 푸시 방식 지원 [#440](https://github.com/moesnow/March7thAssistant/pull/440)
- 개척력 상한 300으로 수정 [#447](https://github.com/moesnow/March7thAssistant/pull/447)
- 몰입기 수량 인식 불가 수정 [#441](https://github.com/moesnow/March7thAssistant/issues/441)
- 뽑기 기록 업데이트 불가 수정
- 일부 코드 규범성 최적화 [#443](https://github.com/moesnow/March7thAssistant/pull/443)

## v2024.12.18

### 업데이트
- "차원 분열 활성화" 시, 2배 횟수 존재하면 개척력 우선 「장신구 추출」 사용
- 그래픽 인터페이스에서 모든 푸시 방식 켜고 끄기 및 설정 지원
- "프레임 잠금 해제" 및 "터치스크린 모드" 오류 메시지 최적화 (게임 이미지 품질을 사용자 정의로 변경 필요)
- "자동 전투 감지 활성화" 시, 게임 시작 전 레지스트리 값 확인 및 수정 시도

## v2024.12.12

### 업데이트
- "터치스크린 모드(클라우드 게임 모바일 UI)"로 게임 시작 지원 (도구함)
- "몰입 보상 수령" 옵션을 "몰입 보상 수령/장신구 추출 실행"으로 변경 (포인트 보상 수령 후 장신구 추출 자동 실행)
- 새 배경화면 "꿈 없는 오늘 밤" 변경 후 우편함 진입 불가 수정
- 종말의 환영 빠른 도전 팁 인식 및 건너뛰기 불가 수정 [#406](https://github.com/moesnow/March7thAssistant/issues/406)

## v2.7.0

### 새로운 기능
- "선데이", "영사" 지원
- 종말의 환영 지원 [#397](https://github.com/moesnow/March7thAssistant/pull/397)
- 부팅 후 자동 실행 지원 (설정-기타)
- 순환 모드 매번 시작 전 설정 파일 다시 로드
- "다중 모니터에서 스크린샷 캡처" 옵션 추가 (설정-기타) [#392](https://github.com/moesnow/March7thAssistant/pull/392)
- HoYoPlay 런처를 통한 게임 설치 경로 자동 획득 지원
- 메인 프로그램 누락 시 오류 메시지 최적화

### 수정
- "일일 임무"가 매번 시작 시 잘못 초기화되던 문제
- "자동 대화" 상태가 변하지 않거나 속도가 너무 느린 문제
- 캐릭터 얼굴 매칭 임계값 낮춤 [#356](https://github.com/moesnow/March7thAssistant/issues/356)

## v2.6.3

### 새로운 기능
- 2.6 버전 신규 스테이지 및 캐릭터(라파) 지원
- "던전 이름" 설정 항목 수동 입력 지원
- 사망으로 인한 도전 실패 시 자동 재시도 지원 [#385](https://github.com/moesnow/March7thAssistant/pull/385)
- 리딤코드 자동 일괄 사용 지원 (도구함)
- "뽑기 기록" "전체 데이터 업데이트" 지원 (잘못된 데이터 수정용)
- 순환 모드 "개척력 기준"(기존) 및 "예약 작업"(지정 시간) 지원
- "ServerChan3" 푸시 방식 지원 [#377](https://github.com/moesnow/March7thAssistant/pull/377)

### 수정
- 뽑기 기록 API 교체
- 수동 수정 설정 파일이 그래픽 인터페이스에 의해 덮어씌워지던 문제 [#341](https://github.com/moesnow/March7thAssistant/issues/341) [#379](https://github.com/moesnow/March7thAssistant/issues/379)
- 게임 창이 다중 모니터 보조 화면에 있을 때 스크린샷 흑백 또는 좌표 밀림 문제 [#378](https://github.com/moesnow/March7thAssistant/pull/378) [#384](https://github.com/moesnow/March7thAssistant/pull/384)
- 다크 모드에서 프로그램 최초 실행 시 계정 목록 배경색 이상
- "화중생화" 이벤트 존재하나 비활성화 시 무한 루프 문제

## v2.5.4

### 새로운 기능
- 2.5 버전 신규 스테이지 지원
- 지원 기능 리개편 (특정 친구의 특정 캐릭터 지원 및 장신구 추출 사용 지원, 재설정 필요)
- "비소", "초구", "운리", "맥택" 지원
- Bilibili 서버 시작 후 "로그인" 자동 클릭 지원 [#321](https://github.com/moesnow/March7thAssistant/discussions/321)
- "임무 완료 후" "재부팅" 옵션 추가

### 수정
- 일부 텍스트 OCR 인식 이상
- 자동 로그인 감지 이상 [#336](https://github.com/moesnow/March7thAssistant/issues/336)
- 고해상도 화면에서 지원 기능 이상 [#329](https://github.com/moesnow/March7thAssistant/issues/329)
- 고치(적) 줄바꿈 오류 수정 [#328](https://github.com/moesnow/March7thAssistant/issues/328)
- 상시 도전 장면 로딩 대기 시간 연장 [#322](https://github.com/moesnow/March7thAssistant/issues/322)
- 장신구 추출 도전 시작 로직 최적화 [#325](https://github.com/moesnow/March7thAssistant/issues/325)
- "시작 실패" 오류 메시지 최적화

## v2.4.0

### 새로운 기능
- 차분 우주 및 장신구 추출 지원
- "지식의 봉오리•페나코니 대극장" 스테이지 지원
- "운리", "Mar. 7th (허수)", "개척자 (허수)" 지원
- Feishu 스크린샷 전송 지원 [#310](https://github.com/moesnow/March7thAssistant/pull/310)

### 수정
- 신규 재료 합성 페이지 멈춤 문제 [#231](https://github.com/moesnow/March7thAssistant/issues/231)

## v2.3.0

### 새로운 기능
- 시뮬레이션 우주 신규 입구 대응 (차분 우주 해금 필요)
- 2.3 버전 신규 스테이지 지원 [#277](https://github.com/moesnow/March7thAssistant/pull/277)
- Bilibili 서버 지원 [#269](https://github.com/moesnow/March7thAssistant/pull/269)
- 글로벌 서버 계정 조작 지원 [#268](https://github.com/moesnow/March7thAssistant/pull/268)
- 상시 도전 및 지원 캐릭터 "반디" 선택 지원
- HoYoPlay 런처 기본 설치 경로 판단 지원

### 수정
- 도시 샌드박스 위치 시 지도 인터페이스 정상 진입 지원
- 혼돈의 기억 갱신 후 팝업으로 인한 실패 확률 문제
- PAC 오류 [#276](https://github.com/moesnow/March7thAssistant/pull/276)

## v2.2.0

### 새로운 기능
- 2.2 버전 신규 스테이지 지원
- 상시 도전 및 지원 캐릭터 "어벤츄린", "로빈" 선택 지원
- 설정에서 시뮬레이션 우주 운명의 길 및 난이도 설정 지원 [#223](https://github.com/moesnow/March7thAssistant/pull/223)
- 설정에서 필드 정리 구매 옵션 설정 지원 [#238](https://github.com/moesnow/March7thAssistant/pull/238)
- 설정 내 다중 계정 관리 기능 추가 [#224](https://github.com/moesnow/March7thAssistant/pull/224)
- 로그인 만료 시 자동 로그인 시도 지원 [#237](https://github.com/moesnow/March7thAssistant/pull/237)
- 템플릿 이미지 메모리 캐시 기본 적용 [#244](https://github.com/moesnow/March7thAssistant/pull/244)
- 뽑기 기록 "비우기" 버튼 추가
- 지원 캐릭터 인터페이스 신규 스타일 대응

### 수정
- "개척자 지원" 및 "의뢰" 인터페이스 전환 불가 [#247](https://github.com/moesnow/March7thAssistant/pull/247)
- 최신 허구 이야기에서 일부 캐릭터 전투 시작 실패 [#242](https://github.com/moesnow/March7thAssistant/pull/242)
- "지원" 및 "별의 선물" 보상 수령 불가
- 특수 상황에서 뽑기 기록 표시 이상 및 튕김

## v2.1.1

### 새로운 기능
- 자동 대화 컨트롤러 인터페이스 대응 [#208](https://github.com/moesnow/March7thAssistant/pull/208)
- Telegram 푸시 프록시 또는 PAC 설정 지원 [#219](https://github.com/moesnow/March7thAssistant/pull/219) [#222](https://github.com/moesnow/March7thAssistant/pull/222)
- 이메일 푸시 outlook 지원 [#220](https://github.com/moesnow/March7thAssistant/pull/220)

### 수정
- 소스 코드 실행 필드 정리 [#211](https://github.com/moesnow/March7thAssistant/pull/211)
- 일부 텍스트 OCR 인식 이상

## v2.1.0

### 새로운 기능
- 2.1 신규 던전 및 이벤트 지원
- 의뢰 보상 일괄 수령으로 변경
- "고치 (적)" 지역 검색으로 변경
- 출석 이벤트 스위치 병합
- 상시 도전 및 지원 캐릭터 "아케론", "갤러거" 선택 지원

### 수정
- 레드 닷이 상시 도전 2번째 방 판단 실패 유발
- 합성 임무가 인터페이스 변경으로 인해 완료 불가
- "고치 (적)" 하위 호환

## v2.0.7

### 새로운 기능
- 사용자 정의 메시지 푸시 형식 지원
- 혼돈의 기억 캐릭터 사망 감지 시 자동 재시도
- 일부 실행 로직 최적화
- 전체 실행 종료 시 남은 개척력 및 예상 회복 시간 알림 (순환 미사용 시) [#197](https://github.com/moesnow/March7thAssistant/pull/197)

### 수정
- 휴대폰 메뉴 아이콘 클릭 이상

## v2.0.6

### 새로운 기능
- 일일 침식된 터널 합성 개수 사용자 정의 지원 [#165](https://github.com/moesnow/March7thAssistant/pull/165)
- 로그 빠른 보기 버튼 추가 [#150](https://github.com/moesnow/March7thAssistant/pull/150)
- "전체 실행" 개척력 소모 전 "의뢰 보상 감지" 추가 [#171](https://github.com/moesnow/March7thAssistant/pull/171)

### 수정
- 던전 검색 시 스크롤 속도 낮춤
- 일부 사용자에게 "'cmd'는 내부 또는 외부 명령이 아닙니다..." 오류로 게임 시작 불가
- 일부 해상도 전체 화면 상태 판단 이상 [#183](https://github.com/moesnow/March7thAssistant/pull/183)

### 기타
- 홈 화면 시뮬레이션 우주 빠른 실행 시 이제 주간 보상도 수령
- 설정 내 필드 정리 및 시뮬레이션 우주 업데이트 버튼 제거 (홈 화면에서 해당 기능 실행하여 업데이트)

## v2.0.5

### 새로운 기능
- "임무 완료 후" "로그오프" 옵션 추가
- 도구함 프레임 잠금 해제 추가 [#161](https://github.com/moesnow/March7thAssistant/pull/161)
- "자동 해상도 변경 활성화" 옵션을 "자동 해상도 변경 및 자동 HDR 끄기 활성화"로 변경 [#156](https://github.com/moesnow/March7thAssistant/pull/156)
- [OneBot](https://onebot.dev) 푸시 알림(QQ 봇) 추가
- 기업용 위챗 앱 푸시 이미지 전송 지원

### 수정
- 일부 상황에서 프레임 잠금 해제 실패
- 일부 상황에서 gotify 알림 전송 실패
- 임무 추적 아이콘으로 인한 지도 인터페이스 인식 불가
- 다수의 레드 닷으로 인한 시뮬레이션 우주 주간 보상 수령 실패
- 빠른 교육 애니메이션 해금으로 인한 허구 이야기 이상
- 홈 화면 Mar. 7th 배경이 높은 배율에서 흐려지는 문제
- 특정 런처가 해상도 레지스트리 수정 후 레지스트리 읽기 오류 발생

## v2.0.4

### 새로운 기능
- 뽑기 기록 내보내기 및 간단 분석 ([SRGF](https://uigf.org/zh/standards/srgf.html) 데이터 형식 가져오기 및 내보내기 지원)
- 상시 도전 및 지원 캐릭터 "스파클" 선택 지원

### 수정
- 특수 상황에서 다운로드 실패

## v2.0.3

### 새로운 기능
- 모든 폰 배경화면 지원
- "자동 스토리" 명칭 "자동 대화"로 변경
- 던전 이름 "없음(건너뛰기)" 옵션 추가
- 1920*1080 이상의 16:9 해상도 지원 (실험적 기능)

### 수정
- 지도 인터페이스 판단 실패
- "자동 해상도 변경" 작동 안 함
- "자동 해상도 변경 활성화" 끄면 게임 시작 불가

## v2.0.2

### 새로운 기능
- 파티 편성 인터페이스 최적화
- 홈 화면 일부 모듈 다중 옵션 지원 (필드 정리, 시뮬레이션 우주, 상시 도전)
- 필드 정리 및 시뮬레이션 우주 설정 파일 초기화 지원
- "게임 리셋 시간", "자동 해상도 변경 활성화", "게임 경로 자동 설정 활성화" 옵션 추가
- 일부 인터페이스 인터넷 재연결 지원

### 수정
- 3D 지도 인터페이스 인식 지원
- 혼돈의 기억 갱신 후 최초 진입 팝업 대응

## v2.0.1

### 새로운 기능
- 유물 던전 완료 후 "4성 이하 유물 자동 분해" 기능 추가 (기본 끔)
- "자동 스토리" 기능 추가 (사이드바 도구함 내 활성화)
- "게임 시작" 버튼 추가 (어시스턴트를 런처로 사용 가능)
- 자동 해상도 변경 지원, 게임 시작 후 원래 해상도 복구
- 사용자 정의 푸시 방식 지원 [#136](https://github.com/moesnow/March7thAssistant/pull/136)

### 수정
- 업데이트 프로그램 덮어쓰기 실패
- 예외 상태에서 전쟁의 여운 3회 미달성 문제
- 경로에 공백이 있어 업데이트 시 브라우저로 이동하는 문제
- 업데이트 프로그램이 Fhoe-Rail\map 디렉토리를 잘못 삭제하는 문제 (이 문제 발생 시 수동으로 개별 업데이트 한 번 클릭)

## v2.0.0

### 새로운 기능
- 2.0 버전 신규 스테이지 지원
- "한정 조기 해금" 스테이지 지원
- "고치 (금) 선호 지역" 선택 지원
- 망각의 정원 및 지원 캐릭터 "Dr. 레이시오", "블랙 스완", "미샤" 선택 지원

### 수정
- 일부 기기 "타오르는 형체" 스테이지 OCR 인식 이상
- "고치 (적)" 임계값 요구사항 낮춤
- "「만능 합성기」 1회 사용" 합성 재료 "미광 원핵"으로 변경
- 버전 업데이트 후 "기억" 전환 이상
- 버전 업데이트 후 "상시 도전" 전환 이상
- 출석 이벤트 이미지 읽기 실패

## v1.7.7

### 새로운 기능
- SMTP 스크린샷 전송 지원 [#114](https://github.com/moesnow/March7thAssistant/pull/114)
- gotify 푸시 방식 지원 [#112](https://github.com/moesnow/March7thAssistant/pull/112)
- "지원 캐릭터 사용 활성화" 옵션 추가 (기본 켜짐) [#121](https://github.com/moesnow/March7thAssistant/issues/121)
- "특정 친구의 지원 캐릭터" 설명 수정 (사용자 이름과 UID 모두 지원)

### 수정
- 원격 데스크톱 다중 실행 시 다른 사용자의 게임 프로세스 잘못 종료 [#113](https://github.com/moesnow/March7thAssistant/pull/113) [#35](https://github.com/moesnow/March7thAssistant/issues/35)
- 일부 텍스트 OCR 인식 이상 (RapidOCR 고치 관련 문제 등)
- 경로에 영문 괄호 포함 시 압축 해제 실패
- 시뮬레이션 우주 완료 후 보상 정상 수령 불가

## v1.7.6

### 새로운 기능
- 화중생화, 기이한 영역, 차원 분열 이벤트 지원 (기본 끔)

## v1.7.5

### 새로운 기능
- 허구 이야기 지원 (기본 스테이지 범위 3-4)

## v1.7.4

### 새로운 기능
- 업데이트 시 풀 패키지 다운로드 지원 (기본 켜짐, 설정→정보)
- 프리뷰 버전 업데이트 채널 참여 지원 (설정→정보)
- 업데이트 시 aria2 멀티스레드 다운로드 지원 (속도 향상 및 중단 감소)
- 업데이트 시 시스템 임시 디렉토리 미사용 (백신 화이트리스트 추가 용이 [#86](https://github.com/moesnow/March7thAssistant/discussions/86#discussioncomment-7966897))

### 수정
- 중복 도전 던전 실행 이상

## v1.7.3

### 새로운 기능
- 망각의 정원 및 지원 캐릭터 "아젠티" 선택 지원
- "자동 전투 감지 활성화" 끄기 지원 (설정→단축키)
- "자동 전투 감지" 시간 무제한으로 변경 (임시 수정 [#96](https://github.com/moesnow/March7thAssistant/pull/96))

### 수정
- 망각의 정원 파티 교체 후 비술 사용 순서 미교체
- 망각의 정원 도전 실패 후 다음 층 도전 시도

## v1.7.2

### 새로운 기능
- 일일 훈련 끄기 지원 (매일 시뮬레이션 우주 1회로 활성도 500 완료 시 활용 가능)
- 신규 전쟁의 여운 「별을 갉아먹는 옛 흉터」 지원
- 망각의 정원 및 지원 캐릭터 "완·매" 선택 지원

### 수정
- 망각의 정원 텔레포트 시 확률적으로 신용 포인트 아이콘 오클릭 [#91](https://github.com/moesnow/March7thAssistant/pull/91)

## v1.7.1


### 수정
- 필드 정리 및 시뮬레이션 우주 실행 이상

## v1.7.0

### 새로운 기능
- 일일 훈련 신규 임무 대응
- 혼돈의 기억 신규 인터페이스 대응 (최초 7층 클리어 후 튜토리얼 수동 완료 필요)
- 혼돈의 기억 캐릭터 선택 화면 스크롤 검색 지원
- 혼돈의 기억 도전 실패 후 자동 파티 교체
- 혼돈의 기억 기본 스테이지 범위 7-12로 변경
- 지원 파티 번호 3-7로 변경
- 망각의 정원 및 지원 캐릭터 "한아", "설의" 선택 지원
- DingTalk 푸시 기본 설정 secret 파라미터 추가

### 수정
- 혼돈의 기억 완료 후 보상 수령 실패

## v1.6.9

### 새로운 기능
- 혼돈의 기억 1-5층 단일 보스 변경 대응

### 수정
- 스크롤 후 지연 부족으로 일부 인터페이스 인식 위치 오차 발생 (또 다시)
- 일부 테스트 코드 제거

## v1.6.8


### 수정
- 시뮬레이션 우주 실행 빈도 설정 이름 오류

## v1.6.7

### 새로운 기능
- 개척력 우선 몰입기 합성 지원 (기본 끔)
- 시뮬레이션 우주 실행 빈도 수정 지원 (기본 매주 1회)

### 수정
- 스크롤 후 지연 부족으로 일부 인터페이스 인식 위치 오차 발생

## v1.6.6

### 새로운 기능
- "일일 훈련" 및 "개척력 소모" 임무 개별 실행 지원
- Fhoe-Rail 업데이트 전 구 map 폴더 자동 삭제

### 수정
- 자동 진형 저장으로 인한 "기억" 및 "혼돈의 기억" 실행 불가
- 일부 희귀 한자 포함 던전 이름 소확률 인식 오류

## v1.6.5

### 새로운 기능
- 시뮬레이션 우주 통합 모드 실행 지원 (기본값)
- 망각의 정원 및 지원 캐릭터 "토파즈&복순이", "계네빈", "곽향" 선택 지원
- 던전 "유부의 형체", "유명의 길" 추가
- 고치 개척력 60 미만 상황 지원 [#31](https://github.com/moesnow/March7thAssistant/pull/31)
- "시작 메뉴" 바로가기에서 게임 경로 가져오기 지원 [#29](https://github.com/moesnow/March7thAssistant/pull/29)

### 수정
- 런처에서 게임 경로 자동 가져오기
- "소모품 사용" 선택 실패 후 재시도 로직 오류 [#41](https://github.com/moesnow/March7thAssistant/pull/41)

## v1.6.4

### 새로운 기능
- 시뮬레이션 우주 주간 실행 횟수 사용자 정의 지원
- "「시뮬레이션 우주」(임의 세계) 1개 구역 클리어" 완료 지원
- 시뮬레이션 우주 무결성 검사 추가 [#27](https://github.com/moesnow/March7thAssistant/pull/27)
- "개척자 (청)•파멸" 및 "개척자 (청)•보존" 지원 [#26](https://github.com/moesnow/March7thAssistant/pull/26)

### 수정
- "게임 종료 실패" 문제 수정 (실험적 변경 롤백)

## v1.6.3

### 새로운 기능
- "히메코 체험"을 통한 일부 일일 훈련 완료 지원 (실험적)
- "기억 1"을 통한 일부 일일 훈련 완료 지원 (실험적)
- Python 3.12.0 강력 구동
- Fhoe-Rail 최신 변경사항 대응

### 수정
- "타임아웃 시간" 소수점 수정 시 그래픽 인터페이스 충돌
- 별의 선물 마지막 날 보상 수령 불가
### 기타
- 기존 기능 안정성 최적화
- 이제 현재 사용자의 게임 프로세스만 종료합니다 (실험적)

## v1.6.2

### 새로운 기능
- "예비 개척력" 및 "연료" 사용 지원
- "별의 선물" 보상 수령 지원
- go-cqhttp 스크린샷 전송 지원 [#21](https://github.com/moesnow/March7thAssistant/pull/21)

### 수정
- 극히 드문 확률로 개척력을 "쌀 미(米)" 자로 인식하는 문제
### 기타
- power_total, dispatch_count, ocr_path 설정 항목 제거
- 배낭 아이템 과다 방지를 위해 소모품 사용 전 카테고리 필터링
- [PaddleOCR-json_v.1.3.1](https://github.com/hiroi-sora/PaddleOCR-json/releases/tag/v1.3.1) 업그레이드, Win7 x64 호환
- [RapidOCR-json_v0.2.0](https://github.com/hiroi-sora/RapidOCR-json/releases/download/v0.2.0/RapidOCR-json_v0.2.0.7z) 지원, AVX 명령어 셋 없는 CPU 호환 (자동 판단)

## v1.6.1

### 새로운 기능
- "던전 이름" 프리셋 (설명 포함)
- "경류" 및 "개척자 (별)•파멸" 지원
- "별의 선물" 보상 수령 지원
- "무명의 공훈 열기" 인터페이스 인식 지원

### 수정
- PushPlus 푸시 [#14](https://github.com/moesnow/March7thAssistant/pull/14)
### 기타
- 휴대폰 배경화면 상태 판단 지원
- "무명의 공훈" 구매 여부 판단 지원
- 파티 설정 진입 방식을 단축키 대신 휴대폰 메뉴로 변경

## v1.6.0

### 새로운 기능
- 혼돈의 기억 완료 후 성옥 보상 자동 수령
- 필드 정리 통합 모드 실행 지원 (기본값)
- 그래픽 인터페이스 테스트 푸시 메시지 기능 추가
- 대부분의 푸시 방식에 필요한 설정 항목 보완 (Bark, ServerChan, 이메일 SMTP 권장)
- 공식 런처에서 게임 경로 가져오기 지원 [#10](https://github.com/moesnow/March7thAssistant/pull/10)

### 수정
- Windows 터미널 상위 버전 "오류 2147942402 (0x80070002)" [#12](https://github.com/moesnow/March7thAssistant/pull/12)
- 저사양 PC에서 의뢰 상태 감지 가끔 이상
- "발생 오류: None" 오류 메시지 최적화
- 시스템 설정 "강조 색 표시" 켜기 시 그래픽 인터페이스 표시 이상 [#11](https://github.com/moesnow/March7thAssistant/pull/11)
### 기타
- 멀티스레딩 사용하여 그래픽 인터페이스 로딩 시간 대폭 단축 [#11](https://github.com/moesnow/March7thAssistant/pull/11)
- Python 버전 감지 및 의존성 설치 최적화
- 내장 "사용 튜토리얼", 웹 버전이 더보기 좋음

## v1.5.0

### 새로운 기능
- 그래픽 인터페이스 내 "던전 이름", "오늘의 훈련" 표시 방식 최적화
- 글로벌 서버 실행 화면(간체 중문) 지원 시도
- "게임 종료", "자동 종료" 등의 기능을 "임무 완료 후"로 통합, 기본값 "없음"
- 순환 실행 4시 시작 시 이제 0-10분 무작위 지연 실행

### 수정
- 업데이트 시 그래픽 인터페이스 자동 종료 안 됨 (파일 점유로 인한 업데이트 실패)
- 작업 디렉토리 불일치 실행 불가 (작업 스케줄러 사용 시 흔함)
### 기타
- 최속 미러 소스 자동 속도 테스트 및 선택
- 이제 "타임아웃" 기능이 "필드 정리", "시뮬레이션 우주" 하위 작업을 올바르게 강제 종료
- conhost 대신 Windows Terminal 우선 사용
- "python_path", "pip_mirror", "github_mirror" 등 설정 항목 사용 중단

## v1.4.2

### 새로운 기능
- [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 자동 필드 정리 프로젝트 내장, 설정 인터페이스에서 개별 업데이트 지원. 제작자에게 Star를 주세요
- 디렉토리 구조 조정, 수동 업데이트 권장, 자동 업데이트는 미사용 파일 제거 안 함

## v1.4.1.1


### 수정
- 가끔 월정액 수령 실패
- 환경 변수에서 Python 경로 자동 가져오기 실패
- pushplus 푸시 문제 (또 다시)

## v1.4.1

### 새로운 기능
- 망각의 정원 및 지원 캐릭터 "부현", "링스" 선택 지원
- 실무 "「망각의 정원」 1회 완료" 끄기 옵션 추가 (기본 끔)
- 임무 완료 후 사운드 알림 재생 지원 (기본 끔)
- Windows 네이티브 알림 지원 (기본 켜짐)
- 일부 오류 메시지 최적화

### 수정
- 필드 정리 원본 실행 오류
- pushplus 푸시 문제

## v1.4.0

### 새로운 기능
- 임무 완료 후 자동 종료 지원 (기본 끔)
- 그래픽 인터페이스 내비게이션 바 최적화
- 그래픽 인터페이스 다크 모드 지원

### 수정
- 던전 텔레포트 클릭 후 대기 시간 연장

## v1.3.5

### 새로운 기능
- 그래픽 인터페이스에서 비술 단축키 수정 지원 [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- 그래픽 인터페이스에서 설정 파일 가져오기 지원 [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- 지정 친구 지원 캐릭터 사용 지원 [#5](https://github.com/moesnow/March7thAssistant/pull/5)
- 다운로드 과정 진행률 표시 지원

### 수정
- 휴대폰 배경화면 변경 시 의뢰 감지 실패

## v1.3.4.2

### 새로운 기능
- 설정 파일에 비술 단축키 수정 추가 [#3](https://github.com/moesnow/March7thAssistant/pull/3)

### 수정
- 차원 분열 이벤트 배너로 인한 헤르타 사무실 자동 진입 불가
- 오수정 방지를 위해 그래픽 인터페이스에서 "던전 필요 개척력" 설정 항목 숨김
- 일일 임무 "「망각의 정원」 1회 완료"에서 멈추는 문제 해결 시도
- 자동 전투 자동 켜기 안 되는 문제 해결 시도

## v1.3.4.1


### 수정
- powershell 명령을 cmd 실행으로 변경
- Python 자동 설치 문제, 이제 정상 설치 가능 (실험적)

## v1.3.4

### 새로운 기능
- 망각의 정원 및 지원 캐릭터 "단항•음월" 선택 지원
- 설정에서 시뮬레이션 우주 및 필드 정리 원본 그래픽 인터페이스 열기 지원 (운명의 길 등 설정용)
- Python, PaddleOCR-json 자동 다운로드 및 설치 지원 (실험적)
- March7thAssistant 및 시뮬레이션 우주 업데이트 기능 최적화 (실험적)

### 수정
- 4K 비 해상도에서 창 모드 실행 시 기능 이상

## v1.3.3.1

### 새로운 기능
- 게임 실행 후 게임 경로 자동 감지 및 저장 지원
- 자주 묻는 질문(FAQ) 업데이트

## v1.3.3

### 새로운 기능
- 무명의 공훈 보상 수령 여부 설정 지원 (기본 끔)
- 더 많은 오류 감지 추가
- 자주 묻는 질문(FAQ) 업데이트

## v1.3.2

### 새로운 기능
- "자동 전투" 자동 켜기 지원
- 필드 정리 및 시뮬레이션 우주 실행 상태 인식 지원
- 게임 업데이트로 인한 재부팅 필요 인식 지원
- 공식 런처가 열려있는 상태에서 게임 시작 지원
- 필드 정리 및 시뮬레이션 우주 스크립트 오류 발생 시 즉시 종료

### 수정
- 임무 실행 후 그래픽 인터페이스 미종료 시, 설정 수정하면 시간 및 일일 상태가 덮어씌워지는 문제
- 게임 시작 후 메인 화면이 아니면 시작 실패로 판정하던 문제 (이제 알려진 임의 화면 지원)

## v1.3.1

### 새로운 기능
- 시뮬레이션 우주 "몰입 보상 수령" 지원, 설정에서 켜기, 기본 끔
- 시뮬레이션 우주 버전 개별 업데이트 지원 (실험적)
- 그래픽 인터페이스 버전 자동 업데이트 지원 (실험적)
- 그래픽 인터페이스 수동 업데이트 확인 지원
- 그래픽 인터페이스 "업데이트 로그", "자주 묻는 질문" 등 하위 페이지 추가

### 수정
- 시뮬레이션 우주 완료 후 알림 스크린샷 최적화

## v1.3.0.2

### 새로운 기능
- v1.3.0에서 제거된 지원 캐릭터 사용(borrow_character_enable) 옵션 복구
- 던전 이름을 "없음"으로 설정하면 해당 실무 임무가 있어도 수행하지 않음

### 수정
- v1.3.0 혼돈의 기억 별 개수 감지 이상

## v1.3.0.1


### 수정
- v1.3.0 그래픽 인터페이스 생성 설정 파일 올바르지 않음

## v1.3.0

### 새로운 기능
- 일일 훈련 내용을 인식하고 전부 수행하는 대신 시도하여 완료 지원 [지원 임무 보기](https://github.com/moesnow/March7thAssistant#%E6%AF%8F%E6%97%A5%E5%AE%9E%E8%AE%AD)
- 매주 "전쟁의 여운" 3회 우선 완료 옵션 추가 (기본 끔)
- 던전 이름(instance_names)을 던전 유형별 개별 설정으로 변경, "xxx 1회 완료" 실무 임무에도 사용
- "지원 캐릭터 사용", "강제 지원 캐릭터 사용", "매일 사진 촬영 활성화", "매일 재료/소모품 합성/사용 활성화" 설정 옵션 제거
- 매주 시뮬레이션 우주 실행 전 수령 가능 보상 확인

### 수정
- 낮은 확률로 던전 이름 인식 실패 문제 해결 시도
- 일일 훈련 전체 완료 감지 신뢰성 문제 완전 해결

## v1.2.6

### 새로운 기능
- 더 많은 던전 유형 지원: 침식된 터널, 응결 허영, 고치 (금), 고치 (적)
- 설정 내 스크린샷 캡처 기능 OCR 텍스트 인식 지원, 던전 이름 복사 용도

## v1.2.5

### 새로운 기능
- 필드 정리 명령 내장

### 수정
- 개척력을 "/240" 대신 "1240"으로 인식하는 경우 수정
- 일일 훈련 전체 완료 감지 실패

## v1.2.4

### 새로운 기능
- 그래픽 인터페이스 업데이트 로그 표시 지원
- 시뮬레이션 우주 업데이트 [Auto_Simulated_Universe v5.30](https://github.com/CHNZYX/Auto_Simulated_Universe/tree/f17c5db33a42d7f6e6204cb3e6e83ec2fd208e5e)

### 수정
- 1.3 버전의 각종 UI 변경으로 인한 이상

## v1.2.3

### 새로운 기능
- 혼돈의 기억 매 스테이지 별 개수 감지 지원
- 던전 이름 약어 지원, 예: [슬기로운 길]

### 수정
- 가끔 클릭 속도가 너무 빨라 실무 보상 수령 실패
- 마우스가 화면 좌측 상단에 위치하여 보안 정책 트리거로 클릭 실패
- 가끔 인터페이스 전환 속도가 너무 느려 소모품 인식 클릭 위치 오프셋
- 무명의 공훈 보상 템플릿 이미지 오류 감지
- 일부 임계값 요구사항 낮춰 조작 성공률 향상
- 일부 불필요한 인터페이스 감지 제거하여 속도 향상

## v1.2.2

### Features
- feat: add Bailu and Kafka
백로 및 카프카 지원
- feat: forgottenhall support melee character
혼돈의 기억 근접 캐릭터 공격 진입 지원
- feat: add take_screenshot to gui
그래픽 인터페이스 설정에 스크린샷 캡처 기능 추가
- feat: add check update to gui
그래픽 인터페이스 시작 시 업데이트 확인
- feat: add tip when start

### Fixes
- fix: use consumables when repeat
소모품 효과 미만료로 사용 불가 문제
- fix: check_update option not available
업데이트 확인 스위치 사용 불가
- fix: avoid trailblaze_power overflow
시뮬레이션 우주 전후 개척력 1회 소모하여 오버플로우 방지
- fix: space cause text ocr fail
가끔 공백 인식으로 텍스트 판단 실패
- fix: exit function

## v1.2.1

### Features
- feat: auto change team
던전 및 필드 정리 전 자동 파티 교체
- feat: add submodule Auto_Simulated_Universe
시뮬레이션 우주 서브모듈 추가

### Fixes
- fix: switch window problem
게임 창 가끔 전경 전환 불가
- fix: same borrow character
지원 캐릭터와 원 파티 캐릭터 동일

## v1.2.0

### Features
- feat: graphical user interface
그래픽 사용자 인터페이스 추가
