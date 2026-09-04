# Windows 구성 참고

## 권장 폴더 구조

에이전트 홈마다 독립된 스크립트 묶음을 둔다.

- Claude: `.claude/hooks-windows`
- Codex: `.codex/hooks-windows`
- Gemini/Antigravity: `.gemini/hooks`

Stop hook은 같은 홈 폴더의 임시 요약 파일을 읽고, 같은 홈 폴더 아래에 TXT와 WAV를 보관해야 한다.

## 음성 provider

세 CLI(Claude, Codex, Gemini/Antigravity) 모두 동일한 provider 옵션을 갖는다. 에이전트 홈의 `TTS-Summary/tts-config.txt`의 `provider`에 다음 값 중 하나를 적으면 `stop-tts.ps1`이 같은 폴더의 provider 스크립트를 호출한다. 값이 없거나 인식되지 않으면 SAPI를 쓴다.

- `windows-sapi`(기본): `play-tts-windows-sapi.ps1`. OS 내장 `System.Speech`. NaturalVoice SAPI Adapter 음성도 지정 가능. 무료·오프라인.
- `gemini-api`: `play-tts-gemini-api.ps1`. 동봉 `assets/tts/gemini_tts.py` + Python(`google-genai` 패키지) + `GEMINI_API_KEY`(유료).
- `elevenlabs-api`: `play-tts-elevenlabs-api.ps1`. 동봉 `assets/tts/elevenlabs_tts.py` + Python(`elevenlabs` 패키지) + `ELEVENLABS_API_KEY`(유료) + `ffmpeg`(MP3 -> WAV 변환 필수).

API provider 스크립트 상단 `$ConverterScript`는 이 스킬에 동봉된 `assets/tts/` 스크립트의 절대 경로로 치환한다(예: `%USERPROFILE%\.claude\skills\agent-cli-tts-summary\assets\tts\gemini_tts.py`).

API provider가 실패하면(키 누락, 네트워크 오류 등) `stop-tts.ps1`이 SAPI provider로 런타임 폴백해 요약이 항상 들리게 한다.

provider별 음성·속도 설정 파일(에이전트 홈, provider 스크립트가 스스로 읽음):

모두 `TTS-Summary/tts-config.txt` 한 파일의 항목이다.

- SAPI 음성: `voice_sapi` (예: `Microsoft Heami Desktop`)
- Gemini 음성: `voice_gemini` (예: `Puck`, `Kore`), 언어 코드: `language_code` (예: `ko-KR`, `en-US`. 요약 언어 선택과 짝을 맞춘다)
- ElevenLabs 음성: `voice_elevenlabs` (예: `Yuna`. 요약 언어에 맞는 음성으로)
- 속도(공통): `speed` (1~10, 소수점 허용). 두 경로가 갈린다. 내장 SAPI는 `ConvertTo-SapiRate`로 Rate = 2 x speed - 10, API provider는 `ConvertTo-TtsTempo`로 배율(speed 5를 1.0으로 두고 그 위로 2.5칸마다 두 배, 10이 4.0)을 구해 `Get-AtempoFilter`가 만든 `ffmpeg atempo` 필터로 적용한다. **SAPI Rate는 규격이 -10~10이라 speed 10이 이미 엔진 최대치이고 더 가팔라질 여지가 없다** — 같은 speed에서 API provider 쪽이 더 빠를 수 있는 것은 이 때문이다. 2.0을 넘는 배율은 체인으로 나눈다(4.0 -> `atempo=2.0,atempo=2.0000`). 최신 ffmpeg는 `atempo`가 0.5~100이라 나눌 필요가 없지만, 옛 빌드는 상한이 2.0이라 단일 필터를 거부하고 그때 속도 설정이 조용히 무시된다
- 사용 여부: `enabled` (`off`면 Stop hook이 재생도 요약 누락 가드도 하지 않는다. 세션 하나만 끄려면 환경 변수 `TTS_SUMMARY=off`로 그 세션을 띄운다. macOS와 같은 분기이며 `references/macos.md` 요약 누락 가드 절 참고), 상세 정도: `verbosity` (1~3. 설정 통지 훅이 있어야 반영된다), 선택지와 중간 보고: `interim` (Windows 기본 `off`. `on`이면 질문 선택지 안내와 중간 phase 보고도 읽는다)

기본 API 구성:

- Gemini: 모델 `gemini-3.1-flash-tts-preview`, 음성 `Puck`
- ElevenLabs: 모델 `eleven_turbo_v2_5`(짧은 요약 기준 v3보다 합성 지연이 짧음), 음성 `Yuna`(한국어)

## 스크립트 인코딩 (UTF-8 with BOM)

`assets/windows/*.ps1`은 한글 주석 때문에 UTF-8 with BOM으로 저장돼 있으며, 복사·수정 시 BOM을 보존해야 한다. BOM이 없으면 Windows PowerShell 5.1이 파일을 ANSI(CP949)로 읽는데, 이때 한글로 끝나는 줄은 마지막 한글의 UTF-8 후행 바이트와 개행 문자가 잘못된 2바이트 쌍으로 소비되면서 다음 줄 전체가 주석에 흡수될 수 있다. 증상은 특정 변수(예: `$ConverterScript`)가 조용히 비어 "Cannot bind argument to parameter 'Path' because it is null" 같은 오류로 나타난다. `stop-tts-wrapper.cmd`는 반대로 BOM 없이 둔다(cmd는 BOM을 명령으로 오독).

## 훅 호출 방식

Claude/Codex는 훅 등록이 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <...>\stop-tts.ps1`로 직접 실행한다(`-File`이어야 요약 누락 가드의 `exit 2`가 전파된다).

Gemini/Antigravity는 wrapper를 거친다.

- 등록: `~/.gemini/settings.json`의 Stop hook이 `powershell.exe ... -File <...>/stop-tts-wrapper.ps1`을 호출한다. Antigravity가 `~/.gemini/config/hooks.json`을 따로 읽는 구성이면 그 파일에는 `stop-tts-wrapper.cmd`를 등록한다(직접 경로 또는 `cmd.exe /c`).
- `stop-tts-wrapper.ps1` 동작: `TTS_NO_PLAY=1`로 `stop-tts.ps1`을 합성 전용 실행(provider 선택·폴백·보관은 stop-tts.ps1 담당) -> 이번 실행에서 생성된 WAV를 WMI 숨김 분리 프로세스로 재생(훅 프로세스 정리 시 재생이 끊기지 않도록) -> 순수 JSON(`{"decision":"proceed"}`)만 stdout으로 출력. 진단은 `log/stop-wrapper.log`.
- 요약 누락 가드는 Claude/Codex 전용이다. Gemini 훅 schema는 `exit 2` 차단 의미가 달라 wrapper가 exit code를 전파하지 않으며, 요약 규율은 `GEMINI.md` 지침이 담당한다.

## 질문 선택지 음성 안내와 중간 phase 보고

두 기능은 설정 파일의 `enabled`와 `interim`이 모두 `on`일 때만 발화한다(Windows 기본 `interim=off`).

- `play-tts-briefing.ps1 "<보고문>"`: 글로벌 지침 블록이 긴 작업의 phase 전환 때 부르는 중간 보고. 설정을 읽어 SAPI 음성·속도를 정한 뒤, 자기 자신을 `-Speak -Rate <n> -Voice <이름> -TextFile <임시 파일>`로 WMI 숨김 분리 프로세스에서 재실행하고 즉시 반환한다. 분리 프로세스는 부모의 환경 변수를 물려받지 않으므로 설정 파일을 다시 읽지 않고 인자만 쓴다. 텍스트는 임시 파일로 넘겨 따옴표·특수문자 문제를 피하고, 읽은 뒤 지운다.
- `ask-question-tts.ps1`: PreToolUse hook. stdin의 `tool_input`(질문 JSON)을 UTF-8로 읽어 "질문: … 선택지는 A, B, 그리고 기타 직접 입력입니다."를 조립하고 같은 폴더의 `play-tts-briefing.ps1`을 위와 같은 방식으로 띄운다. 어떤 경우에도 `exit 0`이라 도구 호출을 막지 않는다. matcher는 Claude `AskUserQuestion`, Codex `request_user_input`.
- 검증: `BRIEFING_TTS_DRYRUN=1`이면 중간 보고가 voice/rate/text를 출력하고, `ASK_TTS_DRYRUN=1`이면 선택지 안내가 조립한 문장을 출력한다. PowerShell에서 JSON을 파이프로 넘기면 부모 콘솔 인코딩으로 재인코딩되어 한글이 깨지므로, 검증은 `cmd /c "powershell ... -File ask-question-tts.ps1 < q.json"`처럼 파일 리디렉션으로 한다(CLI가 훅에 주는 stdin은 UTF-8 바이트 그대로다).

## /tts 슬래시 명령 (Claude Code)

설정 파일을 열지 않고 대화 중에 사용 여부·속도·상세 정도·선택지와 중간 보고 여부를 바꾸는 사용자 스킬이다. 설정기 `assets/windows/tts-config-set.ps1`을 훅 폴더(`~/.claude/hooks-windows`)에 복사하고, `assets/claude/skills/tts/SKILL.windows.md`를 `~/.claude/skills/tts/SKILL.md`로 이름을 바꿔 복사하면 끝난다(설정기는 같은 폴더의 `tts-config.ps1`을 dot-source 한다).

```
/tts                 현재 설정 표시
/tts on | off        음성 요약 켬/끔
/tts speed 8         속도 1~10(소수점 허용)
/tts verbosity 2     상세 정도 1~3
/tts interim off     질문 선택지 안내·중간 phase 보고 끔(응답 완료 요약만). 상세 정도와 무관
```

- SKILL.md의 `` !`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$USERPROFILE\.claude\hooks-windows\tts-config-set.ps1" "$ARGUMENTS"` `` 줄은 Claude Code가 모델 호출 없이 실행해 출력을 컨텍스트에 넣는다. 값 변경은 스크립트가 하고 모델은 결과 한 줄을 전달만 한다.
- `$USERPROFILE`은 `!` 줄을 실행하는 셸이 확장한다(Windows Claude Code의 Git Bash는 확장한다). cmd.exe로 실행되는 환경이면 그 자리에 절대 경로를 박는다.
- 설정기는 macOS 판과 같은 계약을 지킨다: 해당 `키=값` 줄만 바꾸고 주석·다른 키·BOM 유무·줄 끝(CRLF/LF)을 그대로 둔다. 키가 없으면 파일 끝에 덧붙인다. 잘못된 값은 파일을 건드리지 않고 사용법을 출력하며 exit 1.
- 훅이 매 턴 설정 파일을 새로 읽으므로 `/tts off`는 그 턴의 재생부터 꺼진다. `stop-tts.ps1`은 끔 상태에서 남은 `tts-summary.txt`를 지우므로 다음 턴에 이전 요약이 재생되지 않는다.
- `disable-model-invocation: true`라 모델이 스스로 설정을 바꾸지 않는다. 설정은 에이전트 홈에 하나뿐이라 세션별 제어는 아니다.
- 표시 줄은 속도를 SAPI Rate와 함께 보여 준다(예: `속도 7.5(SAPI Rate 5)`). macOS 판이 wpm을 보여 주는 자리와 같다.
- 검증: `python scripts/test_tts_config_set_windows.py`.

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
