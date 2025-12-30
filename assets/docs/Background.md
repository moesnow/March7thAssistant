# 백그라운드 실행

> 원격 로컬 멀티 유저 데스크톱 (컴퓨터 한 대로 가능, 두 대 필요 없음)

 * 에뮬레이터(앱플레이어) 실행은 끊김 현상(렉)이 있고, 성능 소모가 심한 등 여러 단점이 있습니다.
 * Windows 자체 원격 데스크톱 서비스를 사용하여 이 프로그램을 실행하는 것을 권장합니다.
 * 컴퓨터에서 직접 실행하는 것이 에뮬레이터보다 성능 소모가 적습니다.
 * Windows 원격 데스크톱 다중 사용자 활성화 튜토리얼:
   * [상세 튜토리얼 by_Rin](https://www.bilibili.com/read/cv24286313/) (⭐추천⭐)
   * [RDPWrap 방법](https://blog.sena.moe/win10-multiple-RDP/)
   * [파일 수정 방법](https://www.wyr.me/post/701)
 * [상세 튜토리얼 by_Rin](https://www.bilibili.com/read/cv24286313/) 의 모든 관련 파일: [다운로드 링크](https://github.com/CHNZYX/asu_version_latest/releases/download/RDP/LocalRemoteDesktop1.191_by_lin.zip)
   * 예비 링크 (백업)
     * [Baidu Netdisk (바이두 클라우드)](https://pan.baidu.com/s/13aoll4n1gmKlPT9WwNYeEw?pwd=jbha) 추출 코드: jbha
     * [GitHub 미러](https://github.kotori.top/https://github.com/CHNZYX/asu_version_latest/releases/download/RDP/LocalRemoteDesktop1.191_by_lin.zip)



## Windows 11 사용자

[상세 튜토리얼 by_Rin](https://www.bilibili.com/read/cv24286313/)에서 언급된 `SuperRDP` 소프트웨어는 더 이상 사용할 수 없을 수 있으므로, [TermsrvPatcher](https://github.com/fabianosrc/TermsrvPatcher)를 대신 사용하는 것을 권장합니다. 중국 내에서 접속하여 다운로드가 어려운 경우 예비 링크를 통해 다운로드하세요: [Lanzou Cloud](https://wwsj.lanzout.com/i4V8u2np8dna).

**주의:** 이 방법은 [상세 튜토리얼 by_Rin](https://www.bilibili.com/read/cv24286313/)의 `4. 다중 사용자 동시 로그인 패치` 기능만 수행하므로, 나머지 단계는 원본 튜토리얼을 계속 따라주세요.

**사용 방법:**

1. `git clone`을 사용하여 저장소를 복제하거나, 압축 파일을 직접 다운로드합니다.
2. 다운로드가 완료되면 압축을 풀고 `TermsrvPatcher.ps1` 파일을 찾아 우클릭 후 "PowerShell에서 실행"을 선택하면 스크립트가 모든 작업을 자동으로 완료합니다.

또한, 파일을 수동으로 수정하고 싶다면 블로그 게시물: [파일 수정 방법](https://www.wyr.me/post/701)을 참고할 수 있습니다. 단, 해당 블로그의 일부 작업은 Windows 11에서 적용되지 않을 수 있으며, 구체적인 내용은 다음과 같습니다:

- **Windows 11에서 검색해야 할 문자열 (정규식):**
   `39 81 3C 06 00 00 0F (?:[0-9A-F]{2} ){4}00` (실제 작업 시에는 `39 81 3C 06 00 00 0F`만 검색하면 되며, 나머지 16진수 숫자가 정규식과 일치하는지 확인 후 수정하세요)
- **교체할 문자열:**
   `8B 81 38 06 00 00 39 81 3C 06 00 00 75`