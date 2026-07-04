# 문제 해결

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

## Gemini API TTS 실패

`gemini-2.5-flash-tts`가 API-key 기반 `generateContent` 경로에서 404를 반환하면, 현재 key와 endpoint에서 사용 가능한 모델인지 확인한다. 검증된 구성에서는 로컬 Converters 스크립트를 통해 `gemini-3.1-flash-tts-preview`가 동작했다.

비대화형 TTS 스크립트에서 `input()`을 무조건 호출하지 않는지도 확인한다. EOF prompt는 음성 생성 뒤에도 훅 실패처럼 보이게 만들 수 있다.
