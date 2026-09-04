# 자산(assets): 검증된 훅·재생 스크립트 템플릿

새 컴퓨터나 새 에이전트에 TTS 요약 루프를 설치할 때 처음부터 작성하지 말고 이 템플릿을 복사해 경로만 치환한다.

각 파일 상단에 이식용 변수(`$AgentDirName` / `AGENT_DIR_NAME`)와 바꿔야 할 곳(`<-- 이식 시 변경`)이 표시돼 있다.

## 파일 지도

| 파일 | 역할 | 대상 |
| --- | --- | --- |
| `windows/tts-config.txt` | **설정 파일 템플릿**. 사용 여부·속도·상세 정도·선택지와 중간 보고 여부(`interim`, Windows 기본 off)·프로바이더·음성을 담는 유일한 정본. 에이전트 홈의 `TTS-Summary/`에 복사한다 | Windows 세 CLI 공통 |
| `windows/tts-config.ps1` | 설정 파서(`Get-TtsConfig`/`Test-TtsEnabled`/`Test-TtsInterimEnabled`/`Get-TtsProvider`/`ConvertTo-SapiRate`/`ConvertTo-TtsTempo`/`Get-AtempoFilter`). 훅·provider 스크립트가 dot-source 한다 | Windows 세 CLI 공통 |
| `windows/ask-question-tts.ps1` | 선택 질문 도구 호출 직전 질문·선택지 라벨을 조립해 SAPI로 안내(PreToolUse hook). `interim=off`면 발화하지 않는다. 같은 폴더의 `play-tts-briefing.ps1`을 숨김 분리 프로세스로 띄우므로 둘을 함께 둔다 | Claude·Codex(Windows, 선택) |
| `windows/play-tts-briefing.ps1` | 긴 작업의 중간 phase 보고를 SAPI로 분리 재생. 설정의 `enabled`·`interim`·`voice_sapi`·`speed`를 읽고, 자기 자신을 `-Speak`로 숨김 재실행해 훅과 에이전트를 붙잡지 않는다 | Windows 공통 |
| `windows/tts-config-set.ps1` | 설정기. `on`/`off`, `speed <1~10>`, `verbosity <1~3>`, `interim on/off`로 설정 파일의 해당 줄만 바꾸고(주석·BOM·줄 끝 보존) 적용된 설정을 한 줄로 출력한다. 인자 없으면 현재 설정 표시. `tts-config.ps1`을 dot-source 하므로 같은 폴더에 둔다 | Windows 공통(선택, `/tts`가 호출) |
| `windows/tts-replay.ps1` | `/tts-replay` 재생기. `TTS-Summary\wav`의 최신 WAV를 숨김 분리 프로세스로 다시 틀고, 이 턴의 요약 재생을 막기 위해 `tts-summary.txt`를 공백만 담아 써 둔다. `tts-config.ps1`을 dot-source 하므로 같은 폴더에 둔다 | Claude(Windows, 선택) |
| `windows/tts-config-context.ps1` | UserPromptSubmit hook. 매 턴 설정의 사용 여부·상세 정도를 `[tts-config]` 한 줄로 에이전트에 알린다 | Claude(Windows) |
| `windows/stop-tts.ps1` | 임시 요약을 읽고 설정의 `provider`로 고른 provider로 재생, TXT/WAV를 최신 10개로 보관. 설정이 `enabled=off`면 아무것도 하지 않고 종료. API provider 실패 시 SAPI 폴백. 요약 누락 시 `exit 2` 재작성 요구 가드 포함. 공백뿐인 요약 파일(`/tts-replay`가 써 둔 것)은 보관 없이 조용히 통과 | Claude·Codex·Gemini 공통 |
| `windows/play-tts-windows-sapi.ps1` | System.Speech(SAPI/NaturalVoice)로 WAV 생성·재생. 무료·오프라인 | 세 CLI 공통 기본 + 폴백 |
| `windows/play-tts-gemini-api.ps1` | 동봉 `tts/gemini_tts.py`로 Gemini API 음색 사용 + ffmpeg 속도 보정 | 세 CLI 공통(선택, 유료) |
| `windows/play-tts-elevenlabs-api.ps1` | 동봉 `tts/elevenlabs_tts.py`로 ElevenLabs API 음색 사용, ffmpeg로 MP3 -> WAV 변환 + 속도 보정 | 세 CLI 공통(선택, 유료) |
| `windows/stop-tts-wrapper.ps1` | Gemini/Antigravity용 wrapper. `stop-tts.ps1`을 합성 전용(TTS_NO_PLAY)으로 돌리고, 생성된 WAV를 숨김 분리 프로세스로 재생한 뒤 순수 JSON만 stdout으로 낸다(훅 종료 시 재생 끊김 방지) | Gemini·Antigravity |
| `windows/stop-tts-wrapper.cmd` | `.cmd` 등록 경로용 wrapper. 위 ps1 wrapper를 호출해 JSON stdout을 그대로 전달한다(Antigravity `config/hooks.json`의 직접 명령·`cmd.exe /c` 등록에 사용) | Gemini·Antigravity |
| `macos/tts-config.txt` | **설정 파일 템플릿**(macOS판. `provider=say`, `voice_say`) | macOS 공통 |
| `macos/tts-config.sh` | 설정 파서(`tts_config_load`/`tts_enabled`/`tts_interim_enabled`/`tts_provider`/`tts_tempo`/`tts_rate_wpm`/`tts_atempo_filter`). 훅·provider 스크립트가 source 한다 | macOS 공통 |
| `macos/tts-config-context.sh` | UserPromptSubmit hook. 매 턴 설정의 사용 여부·상세 정도를 알린다. Claude는 일반 텍스트, Codex는 `hookSpecificOutput.additionalContext` JSON을 사용한다 | Claude·Codex(macOS) |
| `macos/stop-tts.sh` | 설정의 `provider`로 고른 provider로 재생(기본 `say` + `afconvert`/`afplay`), API provider 실패 시 `say` 폴백. 요약 누락 시 `exit 2`로 재작성 요구 가드 포함. 공백뿐인 요약 파일(`/tts-replay`가 써 둔 것)은 보관 없이 조용히 통과 | macOS 공통 |
| `macos/play-tts-gemini-api.sh` | 동봉 `tts/gemini_tts.py`로 Gemini API 음색 사용 | macOS 공통(선택, 유료) |
| `macos/play-tts-elevenlabs-api.sh` | 동봉 `tts/elevenlabs_tts.py`로 ElevenLabs API 음색 사용. ffmpeg 있으면 WAV 변환, 없으면 MP3 재생 | macOS 공통(선택, 유료) |
| `tts/gemini_tts.py` | Gemini API TTS 변환 스크립트(동봉 사본. 원본: speech-toolkit https://github.com/Engccer/speech-toolkit ). `google-genai` 패키지 필요 | API provider 공용(복사하지 않고 절대 경로로 참조) |
| `tts/elevenlabs_tts.py` | ElevenLabs API TTS 변환 스크립트(동봉 사본, 원본 동일). `elevenlabs` 패키지 필요 | API provider 공용(복사하지 않고 절대 경로로 참조) |
| `macos/ask-question-tts.sh` | 선택 질문 도구 호출 직전 질문·선택지 라벨을 `say`로 백그라운드 안내(PreToolUse hook). 설정의 `interim=off`면 발화하지 않는다. `tts-config.sh`를 source 하므로 같은 폴더에 둔다. matcher는 에이전트별 도구명(Claude `AskUserQuestion`, Codex `request_user_input`), payload는 동형이라 스크립트는 공용 | macOS 공통(선택) |
| `macos/play-tts-briefing.sh` | 긴 작업의 중간 phase 보고를 `say`로 비동기 재생. 설정 파일의 `enabled`·`interim`·`voice_say`·`speed`를 그대로 사용 | macOS 공통 |
| `macos/tts-config-set.sh` | 설정기. `on`/`off`, `speed <1~10>`, `verbosity <1~3>`, `interim on/off`로 설정 파일의 해당 줄만 바꾸고(주석 보존) 적용된 설정을 한 줄로 출력한다. 인자 없으면 현재 설정 표시. `tts-config.sh`를 source 하므로 같은 폴더에 둔다 | macOS 공통(선택, `/tts`가 호출) |
| `macos/tts-replay.sh` | `/tts-replay` 재생기. `TTS-Summary/wav`의 최신 파일(wav/aiff/mp3)을 `afplay`로 분리 재생하고, 이 턴의 요약 재생을 막기 위해 `tts-summary.txt`를 공백만 담아 써 둔다. `tts-config.sh`를 source 하므로 같은 폴더에 둔다 | Claude(macOS, 선택) |
| `claude/skills/tts/SKILL.md` | Claude Code `/tts` 슬래시 명령(macOS 판). `!` 접두 줄로 `~/.claude/hooks/tts-config-set.sh`를 모델 호출 없이 실행한다. `~/.claude/skills/tts/SKILL.md`로 복사한다 | Claude(macOS, 선택) |
| `claude/skills/tts/SKILL.windows.md` | 같은 명령의 Windows 판. `!` 접두 줄이 `powershell.exe -File "$USERPROFILE\.claude\hooks-windows\tts-config-set.ps1"`를 실행한다. **`~/.claude/skills/tts/SKILL.md`라는 이름으로** 복사한다(파일명을 바꿔야 스킬로 인식된다) | Claude(Windows, 선택) |
| `claude/skills/tts-replay/SKILL.md` | Claude Code `/tts-replay` 슬래시 명령(macOS 판). `!` 줄로 `~/.claude/hooks/tts-replay.sh`를 실행하고 모델에게 이 턴의 요약을 쓰지 말라고 지시한다. `~/.claude/skills/tts-replay/SKILL.md`로 복사한다 | Claude(macOS, 선택) |
| `claude/skills/tts-replay/SKILL.windows.md` | 같은 명령의 Windows 판. `hooks-windows\tts-replay.ps1`을 실행한다. **`~/.claude/skills/tts-replay/SKILL.md`라는 이름으로** 복사한다 | Claude(Windows, 선택) |
| `hooks/claude.windows.settings.json` | Windows Claude `~/.claude/settings.json`의 Stop + PreToolUse + UserPromptSubmit 블록 | Claude(Windows) |
| `hooks/claude.macos.settings.json` | macOS Claude `~/.claude/settings.json`의 Stop + PreToolUse + UserPromptSubmit 블록 | Claude(macOS) |
| `hooks/codex.windows.hooks.json` | Windows Codex `~/.codex/hooks.json` (Stop + `request_user_input` PreToolUse) | Codex(Windows) |
| `hooks/codex.macos.hooks.json` | macOS Codex `~/.codex/hooks.json` (Stop + `request_user_input` PreToolUse + 설정 통지 UserPromptSubmit) | Codex(macOS) |
| `hooks/gemini.windows.settings.json` | Windows Gemini `~/.gemini/settings.json`의 hooks 블록(wrapper 경유). macOS Gemini 샘플은 없다(`references/macos.md` 참고) | Gemini·Antigravity(Windows) |

## 설치 순서(Windows 예시)

1. `windows/tts-config.txt`를 대상 에이전트 홈의 `TTS-Summary/tts-config.txt`로 복사한다(이미 있으면 덮어쓰지 않는다). 이 파일이 사용 여부·속도·상세 정도·선택지와 중간 보고 여부(`interim`)·프로바이더·음성의 유일한 정본이다.
2. `stop-tts.ps1`, `play-tts-windows-sapi.ps1`, `tts-config.ps1`, `play-tts-briefing.ps1`을 대상 에이전트 홈의 `hooks-windows`(Gemini는 `hooks`)에 복사하고, 각 파일 상단의 `$AgentDirName`을 해당 폴더명으로 바꾼다(복사한 모든 파일에서 같은 값으로). `tts-config.ps1`은 나머지가 dot-source 하므로 반드시 같은 폴더에 둔다.
3. 고품질 음성을 쓰기로 했으면 `play-tts-gemini-api.ps1` 또는 `play-tts-elevenlabs-api.ps1`도 같은 폴더에 복사해 `$AgentDirName`·`$ConverterScript`를 치환하고, 설정 파일의 `provider`를 `gemini-api` 또는 `elevenlabs-api`로 바꾼다(기본은 `windows-sapi`).
4. Claude면 `tts-config-context.ps1`도 같은 폴더에 두고 UserPromptSubmit 훅으로 등록한다. 이 훅이 있어야 설정의 `verbosity`가 실제 요약 분량에 반영된다(Antigravity에는 이 이벤트가 없어 생략한다). 질문 선택지 안내를 쓰면 `ask-question-tts.ps1`도 같은 폴더에 두고 PreToolUse 훅으로 등록한 뒤 설정 파일의 `interim`을 `on`으로 바꾼다.
5. Claude면 `/tts` 슬래시 명령도 함께 둔다: `windows/tts-config-set.ps1`을 같은 훅 폴더에 복사해 `$AgentDirName`을 맞추고, `claude/skills/tts/SKILL.windows.md`를 `~/.claude/skills/tts/SKILL.md`로 복사한다(파일명을 `SKILL.md`로 바꾼다). `/tts-replay`도 같은 방식으로 둔다: `windows/tts-replay.ps1`을 같은 훅 폴더에, `claude/skills/tts-replay/SKILL.windows.md`를 `~/.claude/skills/tts-replay/SKILL.md`로 복사한다. 새 스킬은 다음 세션부터 `/` 메뉴에 나타난다.
6. Gemini/Antigravity는 `stop-tts-wrapper.ps1`(+`.cmd` 등록 경로를 쓰면 `stop-tts-wrapper.cmd`)도 함께 두고, 훅 등록이 wrapper를 호출하게 한다(`hooks/gemini.windows.settings.json` 참고).
7. `hooks/*.json` 샘플의 경로(사용자명·폴더명)를 환경에 맞게 바꿔 각 에이전트 설정에 병합한다.
8. 설정 파일을 열어 `voice_sapi`(macOS는 `voice_say`)와 `speed`를 환경에 맞게 채운다.
9. `scripts/render_instruction_block.py`로 글로벌 지침 블록을 생성해 `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`에 넣는다(요약 언어를 바꿨으면 `--language` 지정).
10. `scripts/inspect_tts_loop.py`로 설정 파일·폴더·보관본을 점검한다. `경쟁 소비자 발견`이 나오면 기존 `WatchPaths` LaunchAgent 같은 별도 소비자를 해제하고, Stop hook 하나만 `tts-summary.txt`를 읽게 한다. 그 뒤 짧은 응답을 한 번 발생시켜 끝까지 검증한다.

## 주의

- **설정 파일은 하나뿐이다**: 모든 스크립트가 `TTS-Summary/tts-config.txt`를 읽는다.
- **비밀값 금지**: `hooks/*.json` 샘플에는 API 키를 넣지 않았다. 실제 설정 파일(특히 `~/.gemini/settings.json`)에도 비밀값을 함께 두지 말고 환경 변수(`GEMINI_API_KEY`/`ELEVENLABS_API_KEY`)로 주입한다.
- **경로 치환**: `hooks/*.json`의 `<USER_HOME>`은 실제 홈 경로로 바꿔야 한다(`inspect_tts_loop.py`로 확인 후 치환). API provider 스크립트의 `$ConverterScript`/`CONVERTER_SCRIPT`는 이 스킬에 동봉된 `tts/` 스크립트의 절대 경로로 바꾼다(스킬 설치 폴더 기준, 예: `~/.claude/skills/agent-cli-tts-summary/assets/tts/gemini_tts.py`).
- **인코딩(BOM) 보존**: `windows/*.ps1`은 한글 주석 때문에 UTF-8 with BOM이다. BOM이 빠지면 Windows PowerShell 5.1에서 한글로 끝나는 줄이 다음 줄을 삼키는 파싱 오류가 생긴다(`references/troubleshooting.md` 참고). `stop-tts-wrapper.cmd`는 반대로 BOM 없이 유지한다.
- **이식성 요약**: 기본 루프(Windows `stop-tts.ps1` + `play-tts-windows-sapi.ps1`, macOS `stop-tts.sh`)는 외부 참조 없이 그대로 동작한다. API provider 2종도 변환 스크립트는 `tts/`에 동봉돼 있어 별도 저장소가 필요 없고, Python 패키지(`google-genai`/`elevenlabs`) + 해당 API 키(+ Windows ElevenLabs는 `ffmpeg` 필수)만 준비하면 된다. 자세한 분류는 `SKILL.md`의 "이식성 / 외부 의존" 참고.
