# 자산(assets): 검증된 훅·재생 스크립트 템플릿

새 컴퓨터나 새 에이전트에 TTS 요약 루프를 설치할 때 처음부터 작성하지 말고 이 템플릿을 복사해 경로만 치환한다. 모든 스크립트는 실제로 동작 중인 구성에서 추출해 일반화한 것이다.

각 파일 상단에 이식용 변수(`$AgentDirName` / `AGENT_DIR_NAME`)와 바꿔야 할 곳(`<-- 이식 시 변경`)이 표시돼 있다.

## 파일 지도

| 파일 | 역할 | 대상 |
| --- | --- | --- |
| `windows/stop-tts.ps1` | 임시 요약을 읽어 provider로 재생하고 TXT/WAV를 최신 10개로 보관. 요약 누락 시 `exit 2` 재작성 요구 가드 포함(macOS 검증본의 대칭 포팅) | Claude·Codex·Gemini 공통 |
| `windows/play-tts-windows-sapi.ps1` | System.Speech(SAPI/NaturalVoice)로 WAV 생성·재생 | Claude·Codex 기본, Gemini fallback |
| `windows/play-tts-gemini-api.ps1` | speech-toolkit( https://github.com/Engccer/speech-toolkit )의 `TTS/gemini_tts.py`로 Gemini API 음색 사용 + ffmpeg 속도 보정 | Gemini·Antigravity |
| `windows/stop-tts-wrapper.cmd` | 숨김 실행 + JSON stdout 유지 wrapper(빈 콘솔 창·quoting 문제 회피) | Gemini·Antigravity |
| `macos/stop-tts.sh` | `say` + `afconvert`/`afplay` 기반 Stop hook. 요약 누락 시 `exit 2`로 재작성 요구 가드 포함 | macOS 공통 |
| `macos/ask-question-tts.sh` | `AskUserQuestion` 도구 호출 직전 질문·선택지 라벨을 `say`로 백그라운드 안내(PreToolUse hook) | macOS 공통(선택) |
| `hooks/claude.settings.json` | Claude `~/.claude/settings.json`의 Stop hook 블록 | Claude |
| `hooks/codex.hooks.json` | Codex `~/.codex/hooks.json` | Codex |
| `hooks/gemini.settings.json` | Gemini `~/.gemini/settings.json`의 hooks 블록(wrapper 경유) | Gemini·Antigravity |

## 설치 순서(Windows 예시)

1. provider와 `stop-tts.ps1`을 대상 에이전트 홈의 `hooks-windows`(Gemini는 `hooks`)에 복사하고, 각 파일 상단의 `$AgentDirName`을 해당 폴더명으로 바꾼다.
2. Gemini/Antigravity는 `stop-tts-wrapper.cmd`도 함께 두고 stop hook이 wrapper를 호출하게 한다.
3. `hooks/*.json` 샘플의 경로(사용자명·폴더명)를 환경에 맞게 바꿔 각 에이전트 설정에 병합한다.
4. 음성·속도 파일(`tts-voice-sapi.txt`, `tts-speech-rate.txt` 등)을 에이전트 홈에 둔다.
5. `scripts/render_instruction_block.py`로 글로벌 지침 블록을 생성해 `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`에 넣는다.
6. `scripts/inspect_tts_loop.py`로 폴더·보관본을 점검하고, 짧은 응답을 한 번 발생시켜 끝까지 검증한다.

## 주의

- **비밀값 금지**: `hooks/*.json` 샘플에는 API 키를 넣지 않았다. 실제 설정 파일(특히 `~/.gemini/settings.json`)에도 비밀값을 함께 두지 말고 환경 변수(`GEMINI_API_KEY`)로 주입한다.
- **경로 치환**: `hooks/*.json`의 `<USER_HOME>`은 실제 홈 경로로 바꿔야 한다(`inspect_tts_loop.py`로 확인 후 치환). `play-tts-gemini-api.ps1`의 `$ConverterScript`(speech-toolkit 경로)도 새 환경 값으로 바꾼다.
- **이식성 요약**: SAPI 루프(`stop-tts.ps1` + `play-tts-windows-sapi.ps1`)와 macOS `stop-tts.sh`는 외부 참조 없이 그대로 동작한다. Gemini API provider만 speech-toolkit( https://github.com/Engccer/speech-toolkit ) + `GEMINI_API_KEY` + `ffmpeg`를 함께 챙겨야 한다. 자세한 분류는 `SKILL.md`의 "이식성 / 외부 의존" 참고.
