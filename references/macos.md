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

모두 `TTS-Summary/tts-config.txt` 한 파일의 항목이다.

- `say` 음성: `voice_say` (예: `Yuna (Premium)`)
- Gemini 음성: `voice_gemini` (예: `Puck`), 언어 코드: `language_code` (예: `ko-KR`, `en-US`)
- ElevenLabs 음성: `voice_elevenlabs` (예: `Yuna`)
- 속도(공통): `speed` (1~10, 소수점 허용). `tts_rate_wpm`이 `say -r` 값으로(배율 1.0 = 200wpm), `tts_atempo_filter`가 API provider의 `ffmpeg atempo` 필터로 바꾼다. 두 경로가 같은 `tts_tempo`에서 나오므로 provider를 바꿔도 체감 속도가 유지된다. 곡선은 speed 5를 1.0으로 고정하고 그 위로 2.5칸마다 두 배가 되는 기하 곡선이다(5=200wpm, 7.5=400, 10=800). 체감 속도가 비율이라 선형이 아니라 기하로 잡았다. 상한 4.0은 `say`가 800wpm에서 포화하기 때문이다. 2.0을 넘는 배율은 `tts_atempo_filter`가 체인으로 나눈다. 최신 ffmpeg의 `atempo`는 0.5~100을 받아 나눌 필요가 없지만, 옛 빌드는 상한이 2.0이라 단일 필터를 거부하고 그때 속도 설정이 조용히 무시된다(원본 속도로 재생). 버전을 가리지 않게 체인으로 둔다
- 사용 여부: `enabled` (`off`면 Stop hook이 재생도 요약 누락 가드도 하지 않는다. 세션 하나만 끄려면 설정 대신 그 세션을 환경 변수 `TTS_SUMMARY=off`로 띄운다), 상세 정도: `verbosity` (1~3. 설정 통지 훅이 있어야 반영된다), 선택지와 중간 보고: `interim` (macOS 기본 `on`)

## say 음성

가장 단순하고 이식성 높은 macOS provider는 `say`다.

한국어 `say` 음성 예: `Jian (Premium)`, `Minsu (Enhanced)`, `Yuna (Premium)`. 설치된 목록은 `say -v '?'`로 본다. 빠른 재생은 `speed=7.5`(약 400wpm).

사용 가능한 음성 이름은 macOS 버전과 다운로드된 음성에 따라 달라진다. 항상 다음 명령으로 확인한다.

```bash
say -v '?'
```

## 오디오 파일

`say -o`로 오디오 파일을 생성하고 `afconvert`로 WAV로 변환해 보관한다. 속도는 `speed`가 `say -r`로 반영된다(10 = 800wpm 포화). `ffmpeg atempo` 보정은 API provider에만 적용된다.

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
          { "type": "command", "command": "bash <USER_HOME>/.claude/hooks/stop-tts.sh", "timeout": 300 }
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
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "bash <USER_HOME>/.claude/hooks/tts-config-context.sh", "timeout": 10 }
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
- `request_user_input`은 협업 모드 제약이 있다: Default 모드에서는 도구 자체가 비활성이라 모델이 호출할 수 없고, Plan 모드에서 사용된다. 질문 훅을 검증하려면 Plan 모드로 전환한 뒤 선택 질문을 유도한다.
- `UserPromptSubmit`은 macOS Codex에서 발동과 추가 컨텍스트 주입이 동작한다. 일반 텍스트 stdout은 훅 실패가 되므로 `tts-config-context.sh`가 `hookSpecificOutput.additionalContext` JSON을 출력한다.
- Codex 사용자 훅은 새 등록이나 내용 변경 후 신뢰 상태가 `untrusted` 또는 `modified`일 수 있고, 이때 설정에는 있어도 실행 대상에서 빠진다. Codex의 `hooks/list`가 돌려주는 해당 훅의 `currentHash`와 `trustStatus`로 판정한다. 같은 `UserPromptSubmit` 훅이 여러 개면 화면의 `Completed`는 그중 다른 훅의 결과일 수 있으므로, 모델이 실제 `[tts-config]` 문장을 받는지까지 확인한다.
- `tts-summary.txt`를 `WatchPaths`로 감시해 `stop-tts.sh`를 실행하는 LaunchAgent를 Stop hook과 함께 두지 않는다. 두 소비자가 경쟁하면 LaunchAgent 호출에는 Codex payload가 없어서 먼저 파일을 재생·삭제하고, 이어진 정식 Stop hook은 파일 부재를 누락으로 판정해 `exit 2`를 낸다. `scripts/inspect_tts_loop.py`의 `경쟁 소비자 발견` 항목이 비어 있어야 한다.

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "bash <USER_HOME>/.codex/hooks-macos/stop-tts.sh", "timeout": 300, "statusMessage": "Playing Codex TTS summary" }
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
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "bash <USER_HOME>/.codex/hooks-macos/tts-config-context.sh", "timeout": 10 }
        ]
      }
    ]
  }
}
```

### Gemini/Antigravity

macOS Gemini 샘플은 제공하지 않는다. Windows 판(`assets/hooks/gemini.windows.settings.json`)이 wrapper를 쓰는 이유(콘솔 창 숨김, JSON stdout)가 macOS에도 필요한지는 환경마다 다르므로, Windows 샘플의 명령만 bash로 바꿔 붙여넣지 말고 실제 macOS Gemini 환경에서 훅 계약을 확인한 뒤 등록한다.

## 요약 누락 가드

`stop-tts.sh`는 에이전트가 `tts-summary.txt`를 쓰지 않고 턴을 끝내면, 아직 한 번도 재요청하지 않은 경우에 한해 `exit 2`로 응답을 차단하고 요약 작성을 요구한다. Stop hook payload의 `stop_hook_active`가 true면 이미 한 번 재요청한 것이므로 무한루프를 피해 통과한다. 글로벌 지침의 TTS 요약 규칙과 짝을 이뤄 요약 누락을 구조적으로 막는다.

**세션 음소거(`TTS_SUMMARY=off`)**: 병렬 세션에서는 요약 파일이 컴퓨터에 한 벌뿐이라 작업 세션끼리 서로 덮고 남의 훅이 내 요약을 읽어 지운다. 그래서 코디네이터가 있는 병렬 작업은 코디네이터 세션만 요약을 쓰고 작업 세션은 쓰지 않는 것이 규칙이며, 그 세션은 런처가 `TTS_SUMMARY=off claude ...`로 띄운다. 훅은 CLI의 자식 프로세스라 이 변수를 상속하므로 `stop-tts.sh`는 설정을 읽은 직후 `tts_session_muted`면 아무것도 하지 않고 `exit 0`한다. `enabled=off` 분기와 달리 남은 요약 파일을 지우지 않는다(코디네이터가 쓴 파일일 수 있다). 설정 통지 훅은 같은 조건에서 "쓰지 않는다"와 보고 경로(코디네이터 세션)를 매 턴 알린다. 질문 선택지 안내와 중간 phase 보고는 요약 파일을 거치지 않으므로 이 변수의 영향을 받지 않는다. 변수 상속은 재생 없이 확인할 수 있다: `TTS_SUMMARY=off claude -p "확인" --settings <Stop 훅에 env 덤프를 더한 설정>`으로 Stop payload와 함께 변수가 보이고 Stop이 한 번만 호출되면 된다.

설치 후 가드 동작은 재생 없이 직접 검증할 수 있다(요약 파일이 없는 상태에서 실행).

```bash
echo '{"stop_hook_active": false}' | bash ~/.codex/hooks-macos/stop-tts.sh; echo "exit=$?"   # 기대: exit=2
echo '{"stop_hook_active": true}'  | bash ~/.codex/hooks-macos/stop-tts.sh; echo "exit=$?"   # 기대: exit=0
```

## 질문 선택지 음성 안내

`ask-question-tts.sh`는 선택 질문 도구 호출 직전에 발동하는 PreToolUse hook이다(matcher는 에이전트별 실제 도구명: Claude `AskUserQuestion`, Codex `request_user_input`). stdin의 `tool_input`(질문 JSON)을 `python3`로 파싱해 "질문 본문 + 선택지 라벨"을 한국어로 조립하고 `say`로 백그라운드 재생한다. 두 도구의 `tool_input`은 동형(`questions[].question/header` + `options[].label`)이라 스크립트 하나가 양쪽 payload를 그대로 처리한다. 선택지 설명은 스크린리더가 TUI를 탐색하며 읽어 주므로 생략한다. 도구 호출을 절대 차단하지 않으며(어떤 경우에도 `exit 0`), 음성/속도는 `stop-tts.sh`와 같은 설정 파일의 `voice_say`·`speed`를 재사용한다. `ASK_TTS_DRYRUN=1`이면 발화 대신 조립된 문장을 stdout에 출력해 점검할 수 있다. 설정의 `interim=off`면 `play-tts-briefing.sh`와 함께 발화하지 않는다(`enabled`와 별개의 독립 스위치, 상세 정도와 무관).

## /tts 슬래시 명령 (Claude Code)

설정 파일을 열지 않고 대화 중에 사용 여부·속도·상세 정도·선택지와 중간 보고 여부를 바꾸는 사용자 스킬이다. `assets/claude/skills/tts/SKILL.md`를 `~/.claude/skills/tts/SKILL.md`로, 설정기 `assets/macos/tts-config-set.sh`를 `~/.claude/hooks/`로 복사하면 끝난다(설정기는 같은 폴더의 `tts-config.sh`를 source 한다).

```
/tts                 현재 설정 표시
/tts on | off        음성 요약 켬/끔
/tts speed 8         속도 1~10(소수점 허용)
/tts verbosity 2     상세 정도 1~3
/tts interim off     질문 선택지 안내·중간 phase 보고 끔(응답 완료 요약만). 상세 정도와 무관
```

- SKILL.md의 `` !`bash ~/.claude/hooks/tts-config-set.sh "$ARGUMENTS"` `` 줄은 Claude Code가 모델 호출 없이 실행해 출력을 컨텍스트에 넣는다. 값 변경은 스크립트가 하고 모델은 결과 한 줄을 전달만 한다.
- 훅이 매 턴 설정 파일을 새로 읽으므로 `/tts off`는 그 턴의 재생부터 꺼진다. `stop-tts.sh`는 끔 상태에서 남은 `tts-summary.txt`를 지우므로 다음 턴에 이전 요약이 재생되지 않는다.
- `disable-model-invocation: true`라 모델이 스스로 설정을 바꾸지 않는다.
- 설정은 에이전트 홈에 하나뿐이라 세션별 제어는 아니다. 병렬 세션 중 한 창만 끄려면 훅이 받는 세션 ID로 덮어쓰기 계층을 따로 설계해야 한다.
- Codex 커스텀 프롬프트(`~/.codex/prompts/`)는 셸 실행을 지원하지 않아 대응본이 없다. 설정기는 macOS 셸 전용이다.
