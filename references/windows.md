# Windows 구성 참고

## 권장 폴더 구조

에이전트 홈마다 독립된 스크립트 묶음을 둔다.

- Claude: `.claude/hooks-windows`
- Codex: `.codex/hooks-windows`
- Gemini/Antigravity: `.gemini/hooks`

Stop hook은 같은 홈 폴더의 임시 요약 파일을 읽고, 같은 홈 폴더 아래에 TXT와 WAV를 보관해야 한다.

## 음성 provider

세 CLI(Claude, Codex, Gemini/Antigravity) 모두 동일한 provider 옵션을 갖는다. 에이전트 홈의 `tts-provider.txt`에 다음 값 중 하나를 적으면 `stop-tts.ps1`이 같은 폴더의 provider 스크립트를 호출한다. 파일이 없으면 SAPI를 쓴다.

- `windows-sapi`(기본): `play-tts-windows-sapi.ps1`. OS 내장 `System.Speech`. NaturalVoice SAPI Adapter 음성도 지정 가능. 무료·오프라인.
- `gemini-api`: `play-tts-gemini-api.ps1`. speech-toolkit( https://github.com/Engccer/speech-toolkit )의 `TTS/gemini_tts.py` + `GEMINI_API_KEY`(유료).
- `elevenlabs-api`: `play-tts-elevenlabs-api.ps1`. speech-toolkit의 `TTS/elevenlabs_tts.py` + `ELEVENLABS_API_KEY`(유료) + `ffmpeg`(MP3 -> WAV 변환 필수).

API provider가 실패하면(키 누락, 네트워크 오류 등) `stop-tts.ps1`이 SAPI provider로 런타임 폴백해 요약이 항상 들리게 한다.

provider별 음성·속도 설정 파일(에이전트 홈, provider 스크립트가 스스로 읽음):

- SAPI 음성: `tts-voice-sapi.txt` (예: `Microsoft Heami Desktop`)
- Gemini 음성: `tts-voice-gemini.txt` (예: `Puck`, `Kore`), 언어 코드: `tts-language-code.txt` (예: `ko-KR`, `en-US`. 요약 언어 선택과 짝을 맞춘다)
- ElevenLabs 음성: `tts-voice-elevenlabs.txt` (예: `Yuna`. 요약 언어에 맞는 음성으로)
- 속도(공통): `tts-speech-rate.txt` (SAPI Rate -10~10 정수. API provider는 이 값을 `ffmpeg atempo` 배율로 매핑한다. 예: `7` -> `1.7`)

검증된 API 구성:

- Gemini: 모델 `gemini-3.1-flash-tts-preview`, 음성 `Puck` (API-key 기반 `generateContent` 경로에서 동작 확인)
- ElevenLabs: 모델 `eleven_turbo_v2_5`(짧은 요약 기준 v3보다 합성 지연이 짧음), 음성 `Yuna`(한국어)

## 스크립트 인코딩 (UTF-8 with BOM)

`assets/windows/*.ps1`은 한글 주석 때문에 UTF-8 with BOM으로 저장돼 있으며, 복사·수정 시 BOM을 보존해야 한다. BOM이 없으면 Windows PowerShell 5.1이 파일을 ANSI(CP949)로 읽는데, 이때 한글로 끝나는 줄은 마지막 한글의 UTF-8 후행 바이트와 개행 문자가 잘못된 2바이트 쌍으로 소비되면서 다음 줄 전체가 주석에 흡수될 수 있다. 증상은 특정 변수(예: `$ConverterScript`)가 조용히 비어 "Cannot bind argument to parameter 'Path' because it is null" 같은 오류로 나타난다(2026-07-17 실측). `stop-tts-wrapper.cmd`는 반대로 BOM 없이 둔다(cmd는 BOM을 명령으로 오독).

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
