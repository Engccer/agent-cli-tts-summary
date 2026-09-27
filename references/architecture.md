# 구조

## 기본 루프

재사용 가능한 TTS 요약 루프는 다섯 부분으로 구성된다.

1. 글로벌 지침 파일이 에이전트에게 턴 종료 브리핑을 임시 파일에 쓰라고 지시한다.
2. 에이전트가 턴 끝에서 `tts-summary.txt`를 파일 편집으로 작성한다.
3. Stop hook이 턴 종료 후 실행되어 임시 요약 파일을 읽는다.
4. 로컬 TTS 스크립트가 음성을 생성하고 재생한다.
5. 훅이 요약 TXT는 `TTS-Summary/txt`, 음성 WAV는 `TTS-Summary/wav`에 보관하고 각각 최신 10개만 남긴다.

에이전트 본문 응답 중에는 TTS 스크립트를 직접 호출하지 않는다. 직접 재생은 Stop hook의 책임으로 두어야 응답 흐름이 예측 가능하고, 요약 작성과 음성 재생이 분리된다.

## 홈 폴더 경계

가능하면 각 CLI는 자기 홈 폴더 안에 완결된 루프를 가져야 한다.

| 에이전트 | 글로벌 지침 | 임시 요약 | 보관 폴더 |
| --- | --- | --- | --- |
| Claude Code | `.claude/CLAUDE.md` | `.claude/tts-summary.txt` | `.claude/TTS-Summary/txt`, `.claude/TTS-Summary/wav` |
| Codex CLI | `.codex/AGENTS.md` | `.codex/tts-summary.txt` | `.codex/TTS-Summary/txt`, `.codex/TTS-Summary/wav` |
| Antigravity CLI (`agy`) | `.gemini/GEMINI.md` | `.gemini/tts-summary.txt` | `.gemini/TTS-Summary/txt`, `.gemini/TTS-Summary/wav` |
| Gemini CLI (계승됨) | 위와 같은 경로를 쓴다 | 위와 같다 | 위와 같다 |

Gemini CLI는 Antigravity로 통합됐다. Antigravity는 Gemini CLI와 하위 호환이며 확장은 `agy plugin import gemini`로 옮긴다. **홈 폴더는 그대로 `.gemini`이고 글로벌 지침 파일 이름도 `GEMINI.md`라 이 스킬의 경로 설계는 바뀌지 않는다.** 별도 상태 폴더 `.antigravitycli`가 생길 수 있지만 훅과 지침은 `.gemini` 아래를 쓴다.

훅 등록 자리가 Claude·Codex와 다르다. Antigravity는 `~/.gemini/config/hooks.json`을 읽으며 스키마가 **이름 붙인 그룹**이다. 그룹마다 `enabled`로 껐다 켤 수 있고 이벤트 배열 안에 훅 항목이 바로 온다(Claude처럼 `matcher` + 중첩 `hooks` 배열이 아니다).

```json
{
  "antigravity-tts": {
    "enabled": true,
    "Stop": [
      { "type": "command", "command": "<USER_HOME>/.gemini/hooks/stop-tts.sh", "timeout": 60 }
    ]
  }
}
```

⚠ **공식 문서의 이벤트 이름을 믿지 말 것. 배포된 CLI가 구현한 것과 다르다.** Google 문서는 생명주기 이벤트를 `BeforeAgent`·`AfterAgent`·`BeforeTool`·`AfterTool` 등으로 적고 `Stop`을 목록에 넣지 않는다. 그런데 `agy` 1.1.25에 훅을 걸어 직접 재어 보면 **`SessionStart`와 `Stop`만 발동하고** `BeforeAgent`·`AfterAgent`·`UserPromptSubmit`·`PreToolUse`·`SessionEnd`·`Notification`은 발동하지 않는다. 즉 배포된 Antigravity CLI는 Claude Code식 이름을 쓴다.

따라서 이 스킬은 `Stop`을 계속 쓴다. 그리고 **Antigravity에서는 설정 통지(상세 정도 자동 반영)를 쓸 수 없다** — 프롬프트 직후에 컨텍스트를 넣을 이벤트가 실제로 존재하지 않으므로 분량은 `GEMINI.md` 지침 문구로 고정한다. 측정은 `-p` 인쇄 모드 기준이며 대화형 모드에서 더 많은 이벤트가 열릴 가능성은 남아 있다. CLI를 올린 뒤 재생이 멈추면 이벤트 이름부터 다시 재어 본다.

## 재생 provider 선택

세 CLI가 동일한 provider 옵션을 갖는다. 선택은 에이전트 홈의 `TTS-Summary/tts-config.txt`의 `provider` 한 줄로 한다.

| 값 | 음성 | 비용 | 외부 의존 |
| --- | --- | --- | --- |
| `windows-sapi`(Windows 기본) / `say`(macOS 기본) | OS 내장 | 무료·오프라인 | 없음 |
| `gemini-api` | Gemini API TTS | 유료 API | 동봉 `assets/tts/gemini_tts.py`, Python(`google-genai`), `GEMINI_API_KEY`, (속도 보정) ffmpeg |
| `elevenlabs-api` | ElevenLabs API TTS | 유료 API | 동봉 `assets/tts/elevenlabs_tts.py`, Python(`elevenlabs`), `ELEVENLABS_API_KEY`, ffmpeg(Windows 필수, macOS 선택) |

규약: Stop hook은 설정 파일의 `provider`를 읽어 자기와 같은 폴더의 provider 스크립트를 호출한다. 파일이 없거나 값이 인식되지 않으면 OS 내장 provider를 쓴다. provider 스크립트는 성공 시 exit 0, 실패 시 exit 1을 내고, API provider가 실패하면 Stop hook이 OS 내장 provider로 런타임 폴백해 요약이 항상 들리게 한다. 각 provider는 같은 설정 파일에서 자기 음성 항목(`voice_sapi`/`voice_say`, `voice_gemini`+`language_code`, `voice_elevenlabs`)과 `speed`를 스스로 읽으므로 Stop hook은 요약 텍스트만 넘긴다. 설정이 `enabled=off`면 Stop hook이 아무것도 하지 않고 종료한다(요약 누락 가드도 걸지 않는다). 환경 변수 `TTS_SUMMARY=off`로 띄운 세션(병렬 작업 세션)도 같지만 남은 요약 파일을 지우지 않는다(다른 세션 것일 수 있다).

## 요약 언어

요약 언어는 글로벌 지침 블록이 정한다(`scripts/render_instruction_block.py --language`, 기본 한국어). 훅 스크립트는 특정 언어를 강제하지 않으며, 요약 누락 가드 메시지도 "글로벌 지침의 규칙에 따라"라고만 요구한다. 언어를 바꾸면 설정 파일의 음성 항목(`voice_sapi`/`voice_say`, `language_code`, `voice_elevenlabs`)도 그 언어에 맞게 함께 바꾼다.

## 외부 런타임 의존성

이 루프는 외부 TTS CLI나 앱에 런타임 의존하지 않는다. 재생은 OS 내장 기능(Windows SAPI/`System.Speech`, macOS `say`)이나 명시적으로 호출하는 API provider(이 스킬에 동봉된 `assets/tts/gemini_tts.py`·`assets/tts/elevenlabs_tts.py`. 원본: speech-toolkit https://github.com/Engccer/speech-toolkit )만 사용한다. 글로벌 지침에는 실제로 호출되는 도구만 적는다.

## agents/openai.yaml

저장소 루트의 `agents/openai.yaml`은 Codex/OpenAI 계열 에이전트가 이 스킬을 목록에 노출할 때 쓰는 인터페이스 메타데이터(표시 이름, 짧은 설명, 기본 프롬프트)다. Claude Code의 스킬 동작에는 관여하지 않으며, 같은 루프를 여러 에이전트에서 동일하게 부르기 위한 부가 정의일 뿐이다.

## 슬래시 명령 (Claude Code)

- **`/tts` 슬래시 명령 (Claude Code 스킬, macOS·Windows 모두 4단계에서 기본 설치)**: 설정 파일을 열지 않고 대화 중에 사용 여부·속도·상세 정도·선택지·중간 보고 여부를 바꾼다(`/tts off`, `/tts speed 8`, `/tts verbosity 2`, `/tts interim off`, 인자 없으면 현재 설정 표시). SKILL.md의 `!` 접두 줄이 설정기를 모델 호출 없이 실행하므로 결정론적으로 값이 바뀌고, 훅이 매 턴 설정 파일을 새로 읽어 같은 턴의 재생부터 적용된다. `disable-model-invocation: true`라 사용자가 직접 칠 때만 동작한다. 설정은 에이전트 홈마다 하나라 세션별 제어는 아니다. 설정기는 플랫폼별로 둘이다(macOS `tts-config-set.sh`, Windows `tts-config-set.ps1`)이며 SKILL.md도 각각 `SKILL.md`·`SKILL.windows.md`로 나뉜다. macOS Codex는 `/skills` 메뉴와 `$codex-tts`를 통해 모델의 셸 도구가 같은 설정기를 호출한다(`references/codex-commands.md`).
- **`/tts-replay` 슬래시 명령 (Claude Code 스킬, `/tts`와 함께 기본 설치)**: 직전 턴의 요약 음성 파일을 한 번 더 튼다. 새로 합성하지 않고 `TTS-Summary/wav`의 가장 최근 파일을 그대로 재생하므로 API provider여도 비용이 없고, 설정의 `enabled`가 off여도 재생한다. `!` 줄의 재생기(macOS `tts-replay.sh`, Windows `tts-replay.ps1`)가 재생을 분리 프로세스로 넘겨 곧바로 돌아온다. 이 턴도 Stop hook을 지나므로 재생기가 `tts-summary.txt`를 공백만 담아 미리 써 두고, SKILL.md는 모델에게 이 턴에 요약을 쓰지 말라고 지시한다. Stop hook은 공백뿐인 요약 파일을 "이 턴은 재생 없음"으로 보고 보관 없이 조용히 지운다(두 플랫폼 공통 계약). 그래야 "다시 재생했습니다"라는 새 요약이 재생 중인 음성 위에 겹치지 않고, 보관함의 "직전" 자리도 그대로 남아 연속 `/tts-replay`가 같은 요약을 튼다. 세션 음소거(`TTS_SUMMARY=off`) 세션에서는 재생만 하고 요약 파일에 손대지 않는다.
