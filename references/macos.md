# macOS 구성 참고

## 권장 폴더 구조

각 에이전트 홈 안에 shell hook을 둔다.

- Claude: `.claude/hooks`
- Codex: `.codex/hooks-macos`
- Gemini/Antigravity: `.gemini/hooks`

각 훅은 자기 에이전트 홈의 `tts-summary.txt`를 읽고, 같은 홈 아래 보관 폴더에 TXT와 WAV를 저장해야 한다.

## 음성 provider

세 CLI 모두 동일한 provider 옵션을 갖는다. 에이전트 홈의 `TTS-Summary/tts-config.txt`의 `provider`에 다음 값 중 하나를 적으면 `stop-tts.sh`가 같은 폴더의 provider 스크립트를 호출한다. 값이 없거나 인식되지 않으면 `say`를 쓴다.

- `say`(기본): 내장 `say` + `afconvert`/`afplay`. 무료·오프라인.
- `gemini-api`: `play-tts-gemini-api.sh`. 동봉 `assets/tts/gemini_tts.py` + `python3`(`google-genai` 패키지) + `GEMINI_API_KEY`(유료).
- `elevenlabs-api`: `play-tts-elevenlabs-api.sh`. 동봉 `assets/tts/elevenlabs_tts.py` + `python3`(`elevenlabs` 패키지) + `ELEVENLABS_API_KEY`(유료). `ffmpeg`가 있으면 WAV로 변환·속도 보정하고, 없으면 MP3 그대로 `afplay`로 재생한다.

API provider 스크립트 상단 `CONVERTER_SCRIPT`는 이 스킬에 동봉된 `assets/tts/` 스크립트의 절대 경로로 치환한다(예: `~/.claude/skills/agent-cli-tts-summary/assets/tts/gemini_tts.py`).

API provider가 실패하면(키 누락, 네트워크 오류 등) `stop-tts.sh`가 `say`로 런타임 폴백해 요약이 항상 들리게 한다.

provider별 음성·속도 설정 파일(에이전트 홈, provider 스크립트가 스스로 읽음):

모두 `TTS-Summary/tts-config.txt` 한 파일의 항목이다(별도 파일 없음).

- `say` 음성: `voice_say` (예: `Yuna (Premium)`)
- Gemini 음성: `voice_gemini` (예: `Puck`), 언어 코드: `language_code` (예: `ko-KR`, `en-US`)
- ElevenLabs 음성: `voice_elevenlabs` (예: `Yuna`)
- 속도(공통): `speed` (1~10, 소수점 허용). `tts_rate_wpm`이 `say -r` 값으로(배율 1.0 = 200wpm), `tts_tempo`가 API provider의 `ffmpeg atempo` 배율로 바꾼다. 두 경로가 같은 값에서 나오므로 provider를 바꿔도 체감 속도가 유지된다
- 사용 여부: `enabled` (`off`면 Stop hook이 재생도 요약 누락 가드도 하지 않는다), 상세 정도: `verbosity` (1~3. 설정 통지 훅이 있어야 반영된다)

## say 음성

가장 단순하고 이식성 높은 macOS provider는 `say`다.

검증된 macOS 구성의 예시는 다음과 같다.

- Claude 한국어: `Jian (Premium)`
- Codex 한국어: `Minsu (Enhanced)`
- Gemini/Antigravity 한국어: `Yuna (Premium)`
- 빠른 재생 공통 속도: 약 `400` WPM

사용 가능한 음성 이름은 macOS 버전과 다운로드된 음성에 따라 달라진다. 항상 다음 명령으로 확인한다.

```bash
say -v '?'
```

## 오디오 파일

`say -o`로 오디오 파일을 생성하고, 로컬 워크플로우가 WAV 보관을 기대하면 WAV로 변환한다. `say`의 rate만으로 충분히 빠르지 않으면 `ffmpeg` 후처리로 속도를 조정한다.

## 정리 규칙

macOS에서도 Windows와 같은 정리 규칙을 적용한다.

- TXT는 `TTS-Summary/txt`에 보관한다.
- WAV는 `TTS-Summary/wav`에 보관한다.
- 각각 최신 10개만 남긴다.

## 훅 등록

에이전트마다 훅 설정 파일 위치와 이벤트 계약(특히 matcher의 도구명)이 다르다. 아래 예시를 그대로 쓰되 `<USER_HOME>`을 실제 홈 경로로 치환한다(예: `/Users/이름`). 어느 에이전트든 `PreToolUse` 블록(질문 선택지 음성 안내)은 선택이며, 필요 없으면 생략한다.

### Claude Code

`~/.claude/settings.json`의 `hooks` 키에 병합한다. 샘플: `assets/hooks/claude.macos.settings.json`.

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "bash <USER_HOME>/.claude/hooks/stop-tts.sh", "timeout": 60 }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "AskUserQuestion",
        "hooks": [
          { "type": "command", "command": "bash <USER_HOME>/.claude/hooks/ask-question-tts.sh", "timeout": 15 }
        ]
      }
    ]
  }
}
```

### Codex CLI

`~/.codex/hooks.json`에 병합한다. 샘플: `assets/hooks/codex.macos.hooks.json`. Claude 예시에서 경로만 바꾸면 되는 것이 아니라 다음 계약 차이를 반영해야 한다.

- 모든 command hook은 stdin으로 JSON payload를 받는다.
- `Stop` payload에는 `stop_hook_active`가 포함되며, `Stop`에서 exit 2 + stderr 사유는 턴을 한 번 더 진행시키는 제어 신호다(요약 누락 가드가 사용).
- `Stop`에서는 matcher가 사용되지 않는다.
- `PreToolUse` matcher는 실제 로컬 함수 도구명(`tool_name`)을 쓴다. 선택 질문 도구는 `request_user_input`이다. Claude의 `AskUserQuestion`을 등록하면 훅이 절대 발동하지 않는다.
- `request_user_input`은 협업 모드 제약이 있다: Default 모드에서는 도구 자체가 비활성이라 모델이 호출할 수 없고, Plan 모드에서 사용된다(Codex 0.146.0 실측). 질문 훅을 검증하려면 Plan 모드로 전환한 뒤 선택 질문을 유도한다.

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "bash <USER_HOME>/.codex/hooks-macos/stop-tts.sh", "timeout": 60, "statusMessage": "Playing Codex TTS summary" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "request_user_input",
        "hooks": [
          { "type": "command", "command": "bash <USER_HOME>/.codex/hooks-macos/ask-question-tts.sh", "timeout": 15 }
        ]
      }
    ]
  }
}
```

### Gemini/Antigravity

macOS 검증본이 아직 없다. Windows 판(`assets/hooks/gemini.windows.settings.json`)이 wrapper를 쓰는 이유(콘솔 창 숨김, JSON stdout)가 macOS에도 그대로 필요한지 검증되지 않았으므로, Windows 샘플의 명령만 bash로 바꿔 붙여넣지 말고 실제 macOS Gemini 환경에서 검증한 뒤 이 문서와 샘플에 반영한다.

## 요약 누락 가드

`stop-tts.sh`는 에이전트가 `tts-summary.txt`를 쓰지 않고 턴을 끝내면, 아직 한 번도 재요청하지 않은 경우에 한해 `exit 2`로 응답을 차단하고 요약 작성을 요구한다. Stop hook payload의 `stop_hook_active`가 true면 이미 한 번 재요청한 것이므로 무한루프를 피해 통과한다. 글로벌 지침의 TTS 요약 규칙과 짝을 이뤄 요약 누락을 구조적으로 막는다.

설치 후 가드 동작은 재생 없이 직접 검증할 수 있다(요약 파일이 없는 상태에서 실행).

```bash
echo '{"stop_hook_active": false}' | bash ~/.codex/hooks-macos/stop-tts.sh; echo "exit=$?"   # 기대: exit=2
echo '{"stop_hook_active": true}'  | bash ~/.codex/hooks-macos/stop-tts.sh; echo "exit=$?"   # 기대: exit=0
```

## 질문 선택지 음성 안내

`ask-question-tts.sh`는 선택 질문 도구 호출 직전에 발동하는 PreToolUse hook이다(matcher는 에이전트별 실제 도구명: Claude `AskUserQuestion`, Codex `request_user_input`). stdin의 `tool_input`(질문 JSON)을 `python3`로 파싱해 "질문 본문 + 선택지 라벨"을 한국어로 조립하고 `say`로 백그라운드 재생한다. 두 도구의 `tool_input`은 동형(`questions[].question/header` + `options[].label`)이라 스크립트 하나가 양쪽 payload를 그대로 처리한다. 선택지 설명은 스크린리더가 TUI를 탐색하며 읽어 주므로 생략한다. 도구 호출을 절대 차단하지 않으며(어떤 경우에도 `exit 0`), 음성/속도는 `stop-tts.sh`와 같은 설정 파일의 `voice_say`·`speed`를 재사용한다. `ASK_TTS_DRYRUN=1`이면 발화 대신 조립된 문장을 stdout에 출력해 점검할 수 있다.
