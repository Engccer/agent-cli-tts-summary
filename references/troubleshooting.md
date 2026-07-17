# 문제 해결

## 응답 본문이 마지막 한 줄만 보임

에이전트가 본문 답변을 먼저 출력한 뒤 `tts-summary.txt`를 쓰고 짧은 마무리 멘트로 턴을 끝내는 순서 때문이다. Claude Code는 턴의 마지막 텍스트 메시지만 사용자에게 제대로 보여주므로, 본문이 도구 호출 사이 텍스트로 밀려 화면·스크린 리더에서 유실된다(2026-07-17 실측). 해결은 지침 블록의 순서 규칙 적용: 작업·도구 호출 완료 → 요약 파일 Write → 본문 답변을 턴의 마지막 출력으로. 글로벌 지침이 이 순서를 담고 있는지 확인하고, 없으면 `render_instruction_block.py`로 재생성해 반영한다.

## 음성이 재생되지 않음

다음 순서로 확인한다.

1. 에이전트가 비어 있지 않은 `tts-summary.txt`를 작성했는가?
2. Stop hook이 실제로 실행됐는가?
3. 훅이 지침 파일이 쓰라고 한 것과 같은 경로를 읽고 있는가?
4. `TTS-Summary/txt`에 새 TXT 보관본이 생겼는가?
5. `TTS-Summary/wav`에 새 WAV 보관본이 생겼는가?
6. 음성 이름 누락, API key 누락, `ffmpeg` 누락, 비대화형 prompt 같은 이유로 재생 프로세스가 조용히 실패한 것은 아닌가?

## 응답이 한 번 막히고 요약을 쓰라는 메시지가 뜸

요약 누락 가드가 정상 동작하는 신호다. 에이전트가 `tts-summary.txt`를 쓰지 않고 턴을 끝내면 Stop hook이 `exit 2`로 한 번 응답을 되돌려 요약 작성을 요구한다. 에이전트가 요약을 쓰고 다시 끝내면 정상 재생된다. 무한 반복되면 훅 명령이 payload를 stdin으로 받지 못해 `stop_hook_active`를 읽지 못하는 경우다. 훅 등록이 stdin을 전달하는지 확인한다. 이 가드를 끄려면 훅에서 누락 가드 블록을 제거하거나 `exit 2`를 `exit 0`으로 바꾼다.

## 요약 누락 가드가 `exit 2`를 냈는데 재요약 없이 그냥 넘어감

훅이 요약 누락 시 `exit 2`로 응답을 되돌려야 하는데, 에이전트가 재요약을 요구받지 않고 턴이 그대로 끝난다면 스크립트의 종료 코드가 상위 프로세스로 전파되지 않는 경우다. Windows에서 훅을 `powershell.exe ... -Command "& '<path>'"`처럼 스크립트를 `-Command`로 감싸 호출하면 스크립트 안의 `exit 2`가 상위 프로세스에서 다른 코드(흔히 1)로 바뀔 수 있다. 훅 등록은 반드시 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<path>"`처럼 `-File`로 스크립트를 직접 실행해 `exit 2`가 그대로 전파되도록 한다(`-File` 실행에서 `exit 2` 전파, 요약 있을 때 정상 재생, `stop_hook_active`가 true면 통과함을 Windows에서 확인).

## 질문 음성이 안 들리거나 질문 TUI가 지연됨

`ask-question-tts.sh`는 `say`를 백그라운드(`nohup ... &`)로 띄우고 즉시 `exit 0` 하므로 TUI를 지연시키지 않아야 한다. 음성이 전혀 안 나오면 `ASK_TTS_DRYRUN=1`로 실행해 문장이 조립되는지부터 확인하고(파싱 성공 여부), 그 다음 음성/속도 파일과 `say -v '?'`로 음성 이름을 확인한다. 파싱은 `python3`에 의존하므로 `python3`가 PATH에 있어야 한다.

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

## PowerShell 변수가 조용히 비어 있음 (null Path 오류, BOM 누락)

provider 스크립트가 "Cannot bind argument to parameter 'Path' because it is null" 같은 오류로 죽고, 확인해 보면 파일 내용은 멀쩡한데 특정 변수(예: `$ConverterScript`)만 런타임에 비어 있다면, `.ps1` 파일이 UTF-8 without BOM으로 저장된 경우다. Windows PowerShell 5.1은 BOM 없는 파일을 ANSI(한국어 시스템은 CP949)로 읽는데, 한글로 끝나는 줄은 마지막 한글의 UTF-8 후행 바이트와 개행 문자(0x0A)가 잘못된 2바이트 쌍으로 소비되면서 개행이 사라지고 다음 줄 전체가 앞 줄 주석에 흡수된다. 그 줄의 변수 할당이 통째로 사라지는 것이다(2026-07-17 실측: `# <-- 이식 시 변경`처럼 한글로 끝나는 주석 줄 바로 다음 줄이 소실됨). 해결은 `.ps1`을 UTF-8 with BOM으로 저장하는 것. `assets/windows/*.ps1`은 이미 BOM 포함이므로 복사·수정 시 BOM을 보존한다. 요약 누락 가드 메시지의 한글이 깨져 전달되는 문제도 같은 원인·같은 해결이다.

## API provider를 선택했는데 OS 내장 음성으로 들림

런타임 폴백이 동작한 것이다. Stop hook 로그(`log/stop-tts.log`)와 provider 로그(`log/gemini-api-tts.log` 또는 `log/elevenlabs-api-tts.log`)를 확인한다. 흔한 원인: API 키 환경 변수(`GEMINI_API_KEY`/`ELEVENLABS_API_KEY`) 미설정 또는 훅 실행 환경에 미전파, provider 스크립트 상단 `$ConverterScript`/`CONVERTER_SCRIPT`가 placeholder 그대로이거나 **가리키던 스크립트가 이사해 죽은 경로가 된 경우**, API 크레딧 소진(ElevenLabs `quota_exceeded` 401), Windows ElevenLabs 경로에서 `ffmpeg` 없음, 네트워크 오류. provider 로그가 아예 없으면 provider 스크립트가 시작도 못 한 경우이므로 위의 BOM 항목도 의심한다.

실측 사례(2026-07-17): speech-toolkit 분리(2026-07-08)로 옛 `converters/TTS/` 경로가 사라지자, 그 경로를 가리키던 provider가 매턴 조용히 실패하며 9일간 SAPI 폴백으로만 재생되고 있었다. 폴백 덕에 요약은 계속 들려서 아무도 알아채지 못했다. 고품질 음색이 갑자기 OS 내장 음색으로 바뀌었다면 가장 먼저 provider 로그와 `$ConverterScript` 경로 유효성을 확인한다.

## Gemini API TTS 실패

`gemini-2.5-flash-tts`가 API-key 기반 `generateContent` 경로에서 404를 반환하면, 현재 key와 endpoint에서 사용 가능한 모델인지 확인한다. 검증된 구성에서는 speech-toolkit( https://github.com/Engccer/speech-toolkit )의 `gemini_tts.py`를 통해 `gemini-3.1-flash-tts-preview`가 동작했다.

비대화형 TTS 스크립트에서 `input()`을 무조건 호출하지 않는지도 확인한다. EOF prompt는 음성 생성 뒤에도 훅 실패처럼 보이게 만들 수 있다.

## ElevenLabs API TTS 실패

`elevenlabs_tts.py`는 MP3를 출력하므로 Windows에서는 `ffmpeg`가 없으면 provider가 의도적으로 실패한다(`System.Media.SoundPlayer`는 WAV만 재생). macOS는 `afplay`가 MP3를 재생하므로 `ffmpeg` 없이도 동작한다. 모델 기본값은 `eleven_turbo_v2_5`로, 짧은 턴 요약에서는 `eleven_v3`(약 5초)보다 합성 지연이 짧다(약 2초). 음성 이름(`tts-voice-elevenlabs.txt`)이 계정 라이브러리에 없으면 합성이 실패할 수 있으니 `elevenlabs_tts.py --list-voices`로 확인한다.
