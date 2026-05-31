# Windows 구성 참고

## 권장 폴더 구조

에이전트 홈마다 독립된 스크립트 묶음을 둔다.

- Claude: `.claude/hooks-windows`
- Codex: `.codex/hooks-windows`
- Gemini/Antigravity: `.gemini/hooks`

Stop hook은 같은 홈 폴더의 임시 요약 파일을 읽고, 같은 홈 폴더 아래에 TXT와 WAV를 보관해야 한다.

## 음성 provider

Claude와 Codex는 NaturalVoice SAPI Adapter를 통해 Windows SAPI 음성을 사용할 수 있다.

- provider 파일: `tts-provider.txt`
- 한국어 음성 파일: `tts-voice-sapi-ko.txt`
- 영어 음성 파일: `tts-voice-sapi-en.txt`
- 속도 파일: `tts-speech-rate.txt`

Gemini/Antigravity는 구분되는 음색을 위해 Gemini API TTS를 primary provider로 둘 수 있다. 검증된 Windows 구성은 다음과 같다.

- primary provider: Gemini API TTS
- 호출 스크립트: `Converters/TTS/gemini_tts.py`
- 로컬 API key 경로에서 동작 확인된 모델: `gemini-3.1-flash-tts-preview`
- 음성: `Puck`
- 속도 보정: `tts-speech-rate.txt` 값을 `ffmpeg atempo`로 매핑한다. 예: `7` -> `1.7`
- fallback: `Microsoft Heami Desktop` 같은 Windows SAPI 음성

## 훅 호출 방식

CLI 훅 실행 엔진이 안정적으로 실행할 수 있는 단순한 wrapper 명령을 선호한다.

Gemini/Antigravity처럼 훅 schema가 JSON stdout을 기대하는 경우 stdout은 JSON 호환 형태로 깨끗하게 유지한다. 디버그 로그는 파일이나 stderr로 보낸다.

Go 기반 훅 엔진이 PowerShell 직접 실행에서 quoting이나 escaping 문제를 일으키면 `.cmd` wrapper를 두고, wrapper 안에서 명시적 인자로 PowerShell을 호출한다.

## 숨김 재생

Antigravity에서 TTS 재생 시 빈 콘솔 창이 뜨면 재생 helper를 숨김 프로세스로 분리한다.

- PowerShell은 `-WindowStyle Hidden`으로 시작한다.
- wrapper에서 WMI를 사용할 때 `Win32_ProcessStartup.ShowWindow = 0`을 지정한다.
- helper 재생 프로세스에 `Start-Process`를 쓸 경우에도 `-WindowStyle Hidden`을 명시한다.

목표는 CLI 턴이 정상 종료되고, 음성은 재생되며, 추가 터미널 창은 나타나지 않는 상태다.

## 정리 규칙

각 훅 실행이 성공하면 다음을 수행한다.

- 타임스탬프가 붙은 TXT 파일을 `TTS-Summary/txt`에 저장한다.
- 타임스탬프가 붙은 WAV 파일을 `TTS-Summary/wav`에 저장한다.
- TXT와 WAV 모두 오래된 파일을 지워 최신 10개만 남긴다.
