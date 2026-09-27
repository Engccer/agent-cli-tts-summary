# Windows 구성 참고

## 목차

- [권장 폴더 구조](#권장-폴더-구조)
- [설치](#설치)
- [음성 provider](#음성-provider)
- [스크립트 인코딩 (UTF-8 with BOM)](#스크립트-인코딩-utf-8-with-bom)
- [훅 호출 방식](#훅-호출-방식)
- [질문 선택지 음성 안내와 중간 phase 보고](#질문-선택지-음성-안내와-중간-phase-보고)
- [훅 등록](#훅-등록)
- [/tts 슬래시 명령 (Claude Code)](#tts-슬래시-명령-claude-code)
- [/tts-replay 슬래시 명령 (Claude Code)](#tts-replay-슬래시-명령-claude-code)
- [숨김 재생](#숨김-재생)
- [정리 규칙](#정리-규칙)

## 권장 폴더 구조

에이전트 홈마다 독립된 스크립트 묶음을 둔다.

- Claude: `.claude/hooks-windows`
- Codex: `.codex/hooks-windows`
- Gemini/Antigravity: `.gemini/hooks`

Stop hook은 같은 홈 폴더의 임시 요약 파일을 읽고, 같은 홈 폴더 아래에 TXT와 WAV를 보관해야 한다.

## 설치

- `assets/windows/stop-tts.ps1` + `play-tts-windows-sapi.ps1` + `tts-config.ps1`(설정 파서, 나머지가 dot-source 하므로 필수) + `tts-config-context.ps1`(설정 통지, UserPromptSubmit 등록. Antigravity 제외) + `play-tts-briefing.ps1`(지침 블록이 부르는 중간 phase 보고) + `ask-question-tts.ps1`(질문 선택지 안내, PreToolUse 등록)을 대상 홈의 `hooks-windows`(Gemini는 `hooks`)에 둔다. 질문 선택지 안내를 쓰면 설정의 `interim`을 `on`으로 바꾼다(Windows 기본 `off`). API provider를 쓰면 `play-tts-gemini-api.ps1`/`play-tts-elevenlabs-api.ps1`도 같은 폴더에 두고 `$ConverterScript`를 치환한다. Gemini/Antigravity는 `stop-tts-wrapper.ps1`(+`.cmd` 등록 경로면 `stop-tts-wrapper.cmd`)도 함께 둔다. ⚠ `.cmd`는 `$AgentDirName` 변수가 없고 `.gemini` 경로를 직접 박아 두므로 다른 에이전트 홈에 쓸 때는 그 안의 경로 두 줄을 손으로 바꾼다(파일 안 Port note 참고). 변수만 일괄 치환하면 이 파일이 빠진다. Claude면 `/tts` 슬래시 명령용 `tts-config-set.ps1`도 같은 폴더에 둔다(아래 참조). `.ps1`은 UTF-8 with BOM을 보존해 복사한다.
- Claude Code는 `/tts` 슬래시 명령도 기본으로 설치한다: `assets/windows/tts-config-set.ps1`을 훅 폴더(`hooks-windows`)에 두고(`$AgentDirName`은 `.claude`), `assets/claude/skills/tts/SKILL.windows.md`를 `~/.claude/skills/tts/SKILL.md`로 **이름을 바꿔** 복사한다. Windows 판은 `!` 접두 줄이 `powershell.exe -File "$USERPROFILE\.claude\hooks-windows\tts-config-set.ps1"`를 실행하므로, 슬래시 명령의 `!` 줄을 실행하는 셸이 `$USERPROFILE`을 확장하는지(Git Bash면 확장한다) 첫 설치 때 한 번 확인한다. `/tts-replay`도 같은 방식이다: `assets/windows/tts-replay.ps1`을 `hooks-windows`에, `assets/claude/skills/tts-replay/SKILL.windows.md`를 `~/.claude/skills/tts-replay/SKILL.md`로 이름을 바꿔 복사한다.

## 음성 provider

세 CLI(Claude, Codex, Gemini/Antigravity) 모두 동일한 provider 옵션을 갖는다. 에이전트 홈의 `TTS-Summary/tts-config.txt`의 `provider`에 다음 값 중 하나를 적으면 `stop-tts.ps1`이 같은 폴더의 provider 스크립트를 호출한다. 값이 없거나 인식되지 않으면 SAPI를 쓴다.

- `windows-sapi`(기본): `play-tts-windows-sapi.ps1`. OS 내장 `System.Speech`. NaturalVoice SAPI Adapter 음성도 지정 가능. 무료·오프라인.
- `gemini-api`: `play-tts-gemini-api.ps1`. 동봉 `assets/tts/gemini_tts.py` + Python(`google-genai` 패키지) + `GEMINI_API_KEY`(유료). Windows 판은 모델 `gemini-3.1-flash-tts-preview`를 지정하므로 SDK가 필요하고 `language_code`를 넘긴다(macOS 판의 기본 모델과 다르다).
- `elevenlabs-api`: `play-tts-elevenlabs-api.ps1`. 동봉 `assets/tts/elevenlabs_tts.py` + Python(`elevenlabs` 패키지) + `ELEVENLABS_API_KEY`(유료) + `ffmpeg`(MP3 -> WAV 변환 필수).

API provider가 실패하면(키 누락, 네트워크 오류 등) `stop-tts.ps1`이 SAPI provider로 런타임 폴백해 요약이 항상 들리게 한다.

provider별 음성·속도 설정 파일(에이전트 홈, provider 스크립트가 스스로 읽음):

모두 `TTS-Summary/tts-config.txt` 한 파일의 항목이다.

- SAPI 음성: `voice_sapi` (예: `Microsoft Heami Desktop`)
- Gemini 음성: `voice_gemini` (예: `Puck`, `Kore`), 언어 코드: `language_code` (예: `ko-KR`, `en-US`. 요약 언어 선택과 짝을 맞춘다)
- ElevenLabs 음성: `voice_elevenlabs`. 동봉 스크립트의 프리셋 이름(`Yuna`·`DoHyeon`·`Seojin`·`James`·`Kiki`)만 받는다. 요약 언어에 맞는 음성으로
- 속도(공통): `speed` (1~10, 소수점 허용). 두 경로가 갈린다. 내장 SAPI는 `ConvertTo-SapiRate`로 Rate = 2 x speed - 10, API provider는 `ConvertTo-TtsTempo`로 배율(speed 5를 1.0으로 두고 그 위로 2.5칸마다 두 배, 10이 4.0)을 구해 `Get-AtempoFilter`가 만든 `ffmpeg atempo` 필터로 적용한다. SAPI Rate는 규격이 -10~10이라 speed 10이 엔진 최대치다. 그래서 같은 speed에서 API provider 쪽이 더 빠를 수 있고, ElevenLabs는 동봉 스크립트의 자체 기본 속도(1.2배) 위에 atempo가 곱해져 더 빠르다. 2.0을 넘는 배율은 체인으로 나눈다(4.0 -> `atempo=2.0,atempo=2.0000`, 옛 ffmpeg 호환)
- 사용 여부: `enabled` (`off`면 Stop hook이 재생도 요약 누락 가드도 하지 않고 남은 요약 파일을 지운다. 세션 하나만 끄려면 환경 변수 `TTS_SUMMARY=off`로 그 세션을 띄운다. macOS와 같은 분기이며 `references/macos.md` 요약 누락 가드 절 참고), 상세 정도: `verbosity` (1~3. 설정 통지 훅이 있어야 반영된다), 선택지와 중간 보고: `interim` (Windows 기본 `off`. `on`이면 질문 선택지 안내와 중간 phase 보고도 읽는다)

기본 API 구성:

- Gemini: 모델 `gemini-3.1-flash-tts-preview`, 음성 `Puck`
- ElevenLabs: 모델 `eleven_turbo_v2_5`(짧은 요약 기준 v3보다 합성 지연이 짧음), 음성 `Yuna`(한국어)

## 스크립트 인코딩 (UTF-8 with BOM)

`assets/windows/*.ps1`은 한글 주석 때문에 UTF-8 with BOM으로 저장돼 있으며, 복사·수정 시 BOM을 보존해야 한다. BOM이 없으면 Windows PowerShell 5.1이 파일을 ANSI(CP949)로 읽는데, 이때 한글로 끝나는 줄은 마지막 한글의 UTF-8 후행 바이트와 개행 문자가 잘못된 2바이트 쌍으로 소비되면서 다음 줄 전체가 주석에 흡수될 수 있다. 증상은 특정 변수(예: `$ConverterScript`)가 조용히 비어 "Cannot bind argument to parameter 'Path' because it is null" 같은 오류로 나타난다. `stop-tts-wrapper.cmd`는 반대로 BOM 없이 둔다(cmd는 BOM을 명령으로 오독).

## 훅 호출 방식

Claude/Codex는 훅 등록이 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <...>\stop-tts.ps1`로 직접 실행한다(`-File`이어야 요약 누락 가드의 `exit 2`가 전파된다).

Gemini/Antigravity는 wrapper를 거친다.

- 등록: 동작을 확인한 자리는 `~/.gemini/config/hooks.json`의 이름 붙인 그룹이며, 그 파일에는 `stop-tts-wrapper.cmd`를 등록한다(직접 경로 또는 `cmd.exe /c`, timeout 90). `~/.gemini/settings.json`의 hooks 키(`general.hooksConfig.enabled=true`)에 `powershell.exe ... -File <...>/stop-tts-wrapper.ps1`을 함께 둘 수도 있다.
- `stop-tts-wrapper.ps1` 동작: `TTS_NO_PLAY=1`로 `stop-tts.ps1`을 합성 전용 실행(provider 선택·폴백·보관은 stop-tts.ps1 담당) -> 이번 실행에서 생성된 WAV를 WMI 숨김 분리 프로세스로 재생(훅 프로세스 정리 시 재생이 끊기지 않도록) -> 순수 JSON(`{"decision":"proceed"}`)만 stdout으로 출력. 진단은 `log/stop-wrapper.log`.
- 요약 누락 가드는 Claude/Codex 전용이다. Gemini 훅 schema는 `exit 2` 차단 의미가 달라 wrapper가 exit code를 전파하지 않으며, 요약 규율은 `GEMINI.md` 지침이 담당한다.

## 질문 선택지 음성 안내와 중간 phase 보고

두 기능은 설정 파일의 `enabled`와 `interim`이 모두 `on`일 때만 발화한다(Windows 기본 `interim=off`).

- `play-tts-briefing.ps1 "<보고문>"`: 글로벌 지침 블록이 긴 작업의 phase 전환 때 부르는 중간 보고. 설정을 읽어 SAPI 음성·속도를 정한 뒤, 자기 자신을 `-Speak -Rate <n> -Voice <이름> -TextFile <임시 파일>`로 WMI 숨김 분리 프로세스에서 재실행하고 즉시 반환한다. 분리 프로세스는 부모의 환경 변수를 물려받지 않으므로 설정 파일을 다시 읽지 않고 인자만 쓴다. 텍스트는 임시 파일로 넘겨 따옴표·특수문자 문제를 피하고, 읽은 뒤 지운다.
- `ask-question-tts.ps1`: PreToolUse hook. stdin의 `tool_input`(질문 JSON)을 UTF-8로 읽어 "질문: … 선택지는 A, B, 그리고 기타 직접 입력입니다."를 조립하고 같은 폴더의 `play-tts-briefing.ps1`을 위와 같은 방식으로 띄운다. 어떤 경우에도 `exit 0`이라 도구 호출을 막지 않는다. matcher는 Claude `AskUserQuestion`, Codex `request_user_input`.
- 검증: `BRIEFING_TTS_DRYRUN=1`이면 중간 보고가 voice/rate/text를 출력하고, `ASK_TTS_DRYRUN=1`이면 선택지 안내가 조립한 문장을 출력한다. PowerShell에서 JSON을 파이프로 넘기면 부모 콘솔 인코딩으로 재인코딩되어 한글이 깨지므로, 검증은 `cmd /c "powershell ... -File ask-question-tts.ps1 < q.json"`처럼 파일 리디렉션으로 한다(CLI가 훅에 주는 stdin은 UTF-8 바이트 그대로다).

## 훅 등록

샘플은 `assets/hooks/`의 `claude.windows.settings.json`(`~/.claude/settings.json`), `codex.windows.hooks.json`(`~/.codex/hooks.json`), `gemini.windows.settings.json`(`~/.gemini/config/hooks.json`·`~/.gemini/settings.json` 두 형태)이다. `<USER_HOME>`을 실제 홈 경로로 치환해 병합한다. macOS 판(`references/macos.md`)과 다른 점만 적는다.

| 에이전트 | Stop | PreToolUse | UserPromptSubmit |
| --- | --- | --- | --- |
| Claude | `stop-tts.ps1`, timeout 300 | `ask-question-tts.ps1`, matcher `AskUserQuestion`, timeout 10 | `tts-config-context.ps1`, timeout 10 |
| Codex | `stop-tts.ps1`, timeout 300 | `ask-question-tts.ps1`, matcher `request_user_input`, timeout 10 | `tts-config-context.ps1`, timeout 10 |
| Gemini·Antigravity | `config/hooks.json`은 `stop-tts-wrapper.cmd`(timeout 90), `settings.json`은 `stop-tts-wrapper.ps1`(matcher `*`) | 없음 | 없음 |

- **Codex Windows 설정 통지**: `tts-config-context.ps1`의 `$AgentDirName`을 `.codex`로 치환하고 `UserPromptSubmit`에 등록한다. 매 호출마다 설정을 읽어 `hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: "[tts-config] ..."}` JSON을 출력한다. 켬·끔·세션 음소거 모두 같은 출력 계약이며 Claude는 평문을 유지한다.
- [공식 훅 계약](https://learn.chatgpt.com/docs/hooks#userpromptsubmit)은 평문 stdout도 허용하지만 옛 버전 호환을 위해 JSON을 쓴다. Windows Codex CLI 0.153.4 스키마에 해당 이벤트가 있다. 등록 후 `hooks/list`에서 대상 훅의 `trustStatus=trusted`를 확인하고 실제 턴에 `[tts-config]`가 전달되는지 확인한다. 설정 등록이나 스크립트 단독 성공만으로 전달 성공을 판정하지 않는다.
- 검증: `python scripts/test_tts_config_context_windows.py`. 기존 `TTS-Summary/tts-config.txt`는 덮어쓰지 않는다.
- Gemini 샘플의 `settings.json` 형태에는 `timeout` 키가 없고 `config/hooks.json` 형태는 90이다. wrapper가 합성만 하고 재생을 분리 프로세스로 넘겨 즉시 반환하므로 재생 길이에 따른 제한 시간 제약에서 자유롭다.

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
- 설정기는 macOS 판과 같은 계약을 지킨다: 해당 `키=값` 줄만 바꾸고 주석·다른 키·줄 끝(CRLF/LF)을 그대로 둔다. BOM은 Windows 판이 있는 그대로 두고 macOS 판은 벗겨 저장한다. 키가 없으면 파일 끝에 덧붙인다. 잘못된 값은 파일을 건드리지 않고 사용법을 출력하며 exit 1.
- 훅이 매 턴 설정 파일을 새로 읽으므로 `/tts off`는 그 턴의 재생부터 꺼진다. `stop-tts.ps1`은 끔 상태에서 남은 `tts-summary.txt`를 지우므로 다음 턴에 이전 요약이 재생되지 않는다.
- 공통 계약(적용 시점, 세션 음소거와의 관계)은 `references/architecture.md` "슬래시 명령 (Claude Code)".
- 표시 줄은 속도를 SAPI Rate와 함께 보여 준다(예: `속도 7.5(SAPI Rate 5)`). macOS 판이 wpm을 보여 주는 자리와 같다.
- 검증: `python scripts/test_tts_config_set_windows.py`.

## /tts-replay 슬래시 명령 (Claude Code)

직전 턴의 요약 음성 파일을 한 번 더 트는 사용자 스킬이다. 재생기 `assets/windows/tts-replay.ps1`을 훅 폴더(`~/.claude/hooks-windows`)에 복사하고, `assets/claude/skills/tts-replay/SKILL.windows.md`를 `~/.claude/skills/tts-replay/SKILL.md`로 이름을 바꿔 복사하면 끝난다(재생기는 같은 폴더의 `tts-config.ps1`을 dot-source 한다).

- `TTS-Summary\wav`의 가장 최근 WAV를 `System.Media.SoundPlayer`로 튼다.
- 재생은 `stop-tts-wrapper.ps1`과 같은 숨김 분리 프로세스(WMI `Win32_Process`)가 맡아 `!` 줄이 곧바로 돌아온다. 파일이 없을 때도 안내 한 줄과 exit 0으로 끝난다(0이 아니면 스킬 호출이 통째로 중단된다).
- 이 턴의 Stop hook 처리(공백 요약 파일, 세션 음소거)는 `references/architecture.md` "슬래시 명령 (Claude Code)". `stop-tts.ps1`의 요약 누락 가드는 파일이 없을 때만 걸리고 공백뿐인 파일에는 걸리지 않는다.
- 검증: `TTS_REPLAY_DRYRUN=1`로 실행하면 `file=<경로>`와 안내 한 줄을 출력한다. 실제 홈에서는 `TTS_SUMMARY=off`도 함께 줘야 공백 요약 파일을 쓰지 않는다. `python scripts/test_tts_replay_windows.py`, Stop hook 쪽은 `python scripts/test_stop_tts_mute_windows.py`.

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
