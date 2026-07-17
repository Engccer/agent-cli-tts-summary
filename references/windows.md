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

Claude/Codex는 훅 등록이 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <...>\stop-tts.ps1`로 직접 실행한다(`-File`이어야 요약 누락 가드의 `exit 2`가 전파된다).

Gemini/Antigravity는 wrapper를 거친다(2026-07-17 실기기 검증 구성).

- 등록: `~/.gemini/settings.json`의 Stop hook이 `powershell.exe ... -File <...>/stop-tts-wrapper.ps1`을 호출한다. Antigravity가 `~/.gemini/config/hooks.json`을 따로 읽는 구성이면 그 파일에는 `stop-tts-wrapper.cmd`를 등록한다(직접 경로 또는 `cmd.exe /c`).
- `stop-tts-wrapper.ps1` 동작: `TTS_NO_PLAY=1`로 `stop-tts.ps1`을 합성 전용 실행(provider 선택·폴백·보관은 stop-tts.ps1 담당) -> 이번 실행에서 생성된 WAV를 WMI 숨김 분리 프로세스로 재생(훅 프로세스 정리 시 재생이 끊기지 않도록) -> 순수 JSON(`{"decision":"proceed"}`)만 stdout으로 출력. 진단은 `log/stop-wrapper.log`.
- 요약 누락 가드는 Claude/Codex 전용이다. Gemini 훅 schema는 `exit 2` 차단 의미가 달라 wrapper가 exit code를 전파하지 않으며, 요약 규율은 `GEMINI.md` 지침이 담당한다.

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
