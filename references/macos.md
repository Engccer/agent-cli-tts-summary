# macOS 구성 참고

## 권장 폴더 구조

각 에이전트 홈 안에 shell hook을 둔다.

- Claude: `.claude/hooks`
- Codex: `.codex/hooks-macos`
- Gemini/Antigravity: `.gemini/hooks`

각 훅은 자기 에이전트 홈의 `tts-summary.txt`를 읽고, 같은 홈 아래 보관 폴더에 TXT와 WAV를 저장해야 한다.

## 음성 provider

세 CLI 모두 동일한 provider 옵션을 갖는다. 에이전트 홈의 `tts-provider.txt`에 다음 값 중 하나를 적으면 `stop-tts.sh`가 같은 폴더의 provider 스크립트를 호출한다. 파일이 없으면 `say`를 쓴다.

- `say`(기본): 내장 `say` + `afconvert`/`afplay`. 무료·오프라인.
- `gemini-api`: `play-tts-gemini-api.sh`. 동봉 `assets/tts/gemini_tts.py` + `python3`(`google-genai` 패키지) + `GEMINI_API_KEY`(유료).
- `elevenlabs-api`: `play-tts-elevenlabs-api.sh`. 동봉 `assets/tts/elevenlabs_tts.py` + `python3`(`elevenlabs` 패키지) + `ELEVENLABS_API_KEY`(유료). `ffmpeg`가 있으면 WAV로 변환·속도 보정하고, 없으면 MP3 그대로 `afplay`로 재생한다.

API provider 스크립트 상단 `CONVERTER_SCRIPT`는 이 스킬에 동봉된 `assets/tts/` 스크립트의 절대 경로로 치환한다(예: `~/.claude/skills/agent-cli-tts-summary/assets/tts/gemini_tts.py`).

API provider가 실패하면(키 누락, 네트워크 오류 등) `stop-tts.sh`가 `say`로 런타임 폴백해 요약이 항상 들리게 한다.

provider별 음성·속도 설정 파일(에이전트 홈, provider 스크립트가 스스로 읽음):

- `say` 음성: `tts-voice-say.txt` (예: `Yuna (Premium)`), 속도: `tts-rate-wpm.txt` (WPM)
- Gemini 음성: `tts-voice-gemini.txt` (예: `Puck`), 언어 코드: `tts-language-code.txt` (예: `ko-KR`, `en-US`)
- ElevenLabs 음성: `tts-voice-elevenlabs.txt` (예: `Yuna`)
- API provider 속도: `tts-tempo.txt` (배율, 예: `1.3`. `say`의 WPM과 별개이며 `ffmpeg`가 필요)

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

## 훅 등록 (Claude Code 예시)

macOS Claude Code는 `~/.claude/settings.json`의 `hooks` 키에 아래를 병합한다. `<USER_HOME>`을 실제 홈 경로로 치환한다(예: `/Users/이름`). Codex/Gemini는 폴더명(`.codex`/`.gemini`)과 훅 폴더 경로만 바꾼다.

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

Stop hook은 payload를 stdin으로 받아 `stop_hook_active`를 읽어야 요약 누락 가드가 동작한다. `PreToolUse` 블록은 질문 음성 안내가 필요 없으면 생략한다.

## 요약 누락 가드

`stop-tts.sh`는 에이전트가 `tts-summary.txt`를 쓰지 않고 턴을 끝내면, 아직 한 번도 재요청하지 않은 경우에 한해 `exit 2`로 응답을 차단하고 요약 작성을 요구한다. Stop hook payload의 `stop_hook_active`가 true면 이미 한 번 재요청한 것이므로 무한루프를 피해 통과한다. 글로벌 지침의 TTS 요약 규칙과 짝을 이뤄 요약 누락을 구조적으로 막는다.

## 질문 선택지 음성 안내

`ask-question-tts.sh`는 `AskUserQuestion` 도구 호출 직전에 발동하는 PreToolUse hook이다. stdin의 `tool_input`(질문 JSON)을 `python3`로 파싱해 "질문 본문 + 선택지 라벨"을 한국어로 조립하고 `say`로 백그라운드 재생한다. 선택지 설명은 스크린리더가 TUI를 탐색하며 읽어 주므로 생략한다. 도구 호출을 절대 차단하지 않으며(어떤 경우에도 `exit 0`), 음성/속도는 `stop-tts.sh`와 같은 `tts-voice-say.txt`·`tts-rate-wpm.txt`를 재사용한다. `ASK_TTS_DRYRUN=1`이면 발화 대신 조립된 문장을 stdout에 출력해 점검할 수 있다.
