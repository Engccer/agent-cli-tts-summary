# 사례

규칙의 근거가 된 경위와 날짜. 절 제목은 규칙이 있는 문서의 절과 짝이다.

## Antigravity 훅 이벤트 (architecture.md "홈 폴더 경계")

- Gemini CLI는 Antigravity(`agy`)로 통합됐다. 개인 티어(Gemini Code Assist 개인·Google AI Pro·Google AI Ultra)는 2026-06-18에 요청 처리가 끝났다.
- 발동 이벤트는 `Stop`을 대조군으로 둔 `agy -p` 실행에서 쟀다. 대조군만 기록됐다.

## 질문 선택지·중간 보고 음성만 설정 속도보다 느림 (troubleshooting.md, Windows)

PowerShell 변수명은 대소문자를 구분하지 않아 스크립트 안의 `$rate = $null`이 param `$Rate`를 지워 버렸고, 그 결과 SAPI Rate가 0(speed 5 상당)으로 떨어졌다(실측: speed 7.5에서 Stop hook은 Rate 5, 분리 프로세스는 Rate 0). 2026-09-16 수정본은 내부 변수를 `$sapiRate`/`$sapiVoice`로 두어 param과 겹치지 않는다.
