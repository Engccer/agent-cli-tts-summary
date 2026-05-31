# 문제 해결

## 음성이 재생되지 않음

다음 순서로 확인한다.

1. 에이전트가 비어 있지 않은 `tts-summary.txt`를 작성했는가?
2. Stop hook이 실제로 실행됐는가?
3. 훅이 지침 파일이 쓰라고 한 것과 같은 경로를 읽고 있는가?
4. `TTS-Summary/txt`에 새 TXT 보관본이 생겼는가?
5. `TTS-Summary/wav`에 새 WAV 보관본이 생겼는가?
6. 음성 이름 누락, API key 누락, `ffmpeg` 누락, 비대화형 prompt 같은 이유로 재생 프로세스가 조용히 실패한 것은 아닌가?

## Antigravity 재시작 필요

Antigravity는 세션 시작 시점의 훅 설정을 캐시할 수 있다. 훅 JSON 파일이나 wrapper 명령을 수정했다면 현재 세션에서 바로 검증하지 말고, Antigravity CLI를 완전히 종료한 뒤 새 세션에서 테스트한다.

## 한글이 깨져 보임

CLI에 한글이 mojibake 형태로 보이면 훅 stdout 인코딩이나 터미널 code page가 맞지 않을 수 있다. 훅 stdout은 최소화하고, 진단 메시지는 UTF-8 로그 파일에 남긴다.

## PowerShell 명령 escaping 실패

일부 훅 엔진은 대화형 shell과 다르게 command array를 파싱한다. `powershell.exe -File ...` 직접 호출이 실패하면 단순 경로의 `.cmd` wrapper를 만들고, 그 안에서 PowerShell을 명시적 인자로 호출한다.

## 빈 콘솔 창이 뜸

재생 helper를 숨김 프로세스로 만든다.

- PowerShell: `-WindowStyle Hidden`
- WMI: `Win32_ProcessStartup.ShowWindow = 0`
- detached audio playback에 보이는 helper 터미널을 만들지 않는다.

## Gemini API TTS 실패

`gemini-2.5-flash-tts`가 API-key 기반 `generateContent` 경로에서 404를 반환하면, 현재 key와 endpoint에서 사용 가능한 모델인지 확인한다. 검증된 구성에서는 로컬 Converters 스크립트를 통해 `gemini-3.1-flash-tts-preview`가 동작했다.

비대화형 TTS 스크립트에서 `input()`을 무조건 호출하지 않는지도 확인한다. EOF prompt는 음성 생성 뒤에도 훅 실패처럼 보이게 만들 수 있다.

## AgentVibes 언급

스크립트 이름이나 환경 변수에 AgentVibes가 남아 있어도 역사적 흔적일 수 있다. 실제 AgentVibes 실행 파일을 호출하지 않는다면 글로벌 사용자 지침에 AgentVibes를 의존성처럼 적지 않는다.
