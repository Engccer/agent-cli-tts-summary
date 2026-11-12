# 변경 기록

## 1.27.0 (2026-11-13)

- 여러 세션을 동시에 돌려도 요약이 사라지거나 겹치지 않게 했다. 원인은 셋이었다: 모든 세션이 `tts-summary.txt` 하나를 같이 써서 서로 덮어쓰거나 남의 요약을 읽고 지웠고, 재생 순서를 맞추는 장치가 없어 음성이 겹쳤으며, Windows에서는 두 Stop hook이 같은 로그 파일을 동시에 잡으면 뒤쪽이 provider를 실행하지도 못한 채 요약을 지웠다.
- 세션 전용 요약 파일 `TTS-Summary/pending/<세션 식별자>.txt`를 두었다. 설정 통지 훅이 payload의 세션 식별자(Claude·Codex `session_id`, Antigravity `conversationId`)로 경로를 정해 `[tts-config]` 줄에 싣고, Stop hook은 자기 세션 파일을 먼저 읽고 없으면 공용 `tts-summary.txt`로 폴백한다. 누락 가드·`enabled=off` 정리·미리 합성(`tts-presynth.sh`)·공백 억제 파일(`replay`·`read`·`pause`)이 같은 규칙을 따르고, Stop까지 가지 못한 턴의 세션 파일은 하루 뒤 치운다. 글로벌 지침 블록은 요약 경로를 통지 줄에 위임한다.
- 재생 대기열을 두었다. 요약·중간 보고·질문 안내·다시 재생·전문 낭독이 머신 전역 잠금 하나를 차례로 쥐어 세 CLI와 pi의 음성이 먼저 온 것부터 이어서 들린다. Windows는 이름 붙은 뮤텍스(`tts-config.ps1`의 `Enter-TtsPlaybackQueue`, 새 분리 재생기 `play-tts-queued.ps1`), macOS는 `tts_playback.py --queue`의 `flock`이다.
- Windows `stop-tts.ps1`과 Antigravity wrapper는 자식 출력을 변수로 받아 로그에 쓰고, wrapper는 `TTS_AUDIO_PATH_FILE`로 받은 이번 실행의 WAV만 재생한다(보관 폴더의 가장 새 WAV를 고르지 않는다). `stop-tts.ps1`은 payload를 UTF-8로 읽어 한글이 든 payload에서도 세션 식별자를 잃지 않는다.
- macOS 재생 대기열은 차례가 600초 안에 오지 않거나 잠금을 열 수 없으면 기다리지 않고 재생한다. `install_macos_commands.py --update-stop-hook`은 세 CLI 모두 `tts-config-context.sh`를 함께 갱신한다.
- macOS `tts-config-context.sh`가 `CLAUDE_CONFIG_DIR`를 따른다(통지 경로와 Stop hook이 보는 경로를 맞춘다). Claude `tts-replay`·`tts-pause` 스킬은 `"${CLAUDE_SESSION_ID}"`를 인자로 넘긴다.
- 설치본 갱신: macOS는 `install_macos_commands.py --agent <claude|codex|agy> --update-stop-hook`, Windows는 `assets/windows/`의 바뀐 `.ps1`과 `play-tts-queued.ps1`을 훅 폴더에 다시 복사한다. Antigravity는 설정 통지 훅(`PreInvocation`)이 등록돼 있어야 세션 전용 경로를 받는다. Codex는 내용이 바뀐 훅의 신뢰 상태를 확인한다.

## 1.26.1 (2026-11-12)

- 문서 만료 점검: 음소거·폴백·`pause` 범위·Azure 원본과 음성 항목·목차 앵커 등 현재 코드와 어긋난 서술을 고치고, 필수 문서 `CLAUDE.md`·`docs/BACKLOG.md`를 새로 두고 `PROGRESS.md`를 현재 상태로 다시 썼다. `/tts-pause` 스킬 설명에 질문 안내·중간 보고·미리 합성 중지를 더했다.

## 1.26.0 (2026-11-12)

- 요약 음성 미리 합성을 macOS Codex(`PostToolUse` matcher `^apply_patch$`)와 Antigravity(`write_file|edit_file`)로 넓혔다. `tts-presynth.sh`는 도구 입력에서 경로를 뽑는 대신 훅 입력에 `<에이전트 폴더명>/tts-summary.txt`가 있는지로 판정해 세 CLI의 payload 형태 차이를 흡수하고, Antigravity에서는 stdout에 `{}`를 낸다. 캐시 키는 CR을 빼고 계산해 Codex Stop의 줄바꿈 정규화와 맞춘다.
- `install_macos_commands.py --update-stop-hook`이 Codex·Antigravity에도 `tts-presynth.sh`를 설치한다. Codex는 `/hooks`에서 새 훅을 신뢰 승인해야 실행된다.

## 1.25.0 (2026-11-12)

- macOS Claude Code에 요약 음성 미리 합성을 더했다. `PostToolUse`(`Write|Edit|MultiEdit`)로 등록한 `tts-presynth.sh`가 `tts-summary.txt`가 써지는 순간 API provider로 합성해 두고, `stop-tts.sh`는 같은 글의 캐시 음성을 꺼내 바로 재생한다(합성 중이면 기다리고, 없으면 평소대로 합성). 실측상 응답 완료 뒤 대기가 Azure 합성 0.2~1초에서 꺼내기 0.07초로 줄었다.
- `install_macos_commands.py --agent claude --update-stop-hook`이 `tts-presynth.sh`도 설치한다. 훅 등록은 `references/macos.md` 예시를 따른다.

## 1.24.0 (2026-11-12)

- macOS Codex도 API provider 실패나 provider 스크립트 누락 시 중단하지 않고 `say`로 폴백한다. 세 CLI의 폴백 규칙이 같아졌고, 폴백할 때는 `log/stop-tts.log`에 `say로 폴백` 한 줄을 남긴다.

## 1.23.0 (2026-11-12)

- macOS Antigravity(`agy`)의 질문 선택지 안내와 중간 보고도 공용 재생 worker로 옮겨, 세 CLI 모두 설정의 `provider`·음성·속도를 최종 요약과 공유한다. `say` 직접 호출 분기는 없앴다. API 실패 시 Antigravity는 Claude처럼 내장 음성으로 폴백한다.
- `TTS_SUMMARY=off` Antigravity 세션도 질문 안내와 중간 보고를 읽지 않는다. `ask_question` 훅의 stdout은 `{"decision":"allow"}`만 남도록 재생 출력을 버린다.

## 1.22.0 (2026-11-12)

- macOS Claude Code의 질문 선택지 안내(`ask-question-tts.sh`)와 중간 보고(`play-tts-briefing.sh`)가 `voice_say` 내장 음성에 고정돼 있던 것을 Codex와 같은 공용 재생 worker 경로로 옮겨, 설정의 `provider`·음성·속도를 최종 요약과 공유한다. API 실패 시에는 최종 요약과 같이 내장 음성으로 폴백한다.
- `TTS_SUMMARY=off` Claude 세션은 질문 안내와 중간 보고도 읽지 않는다.
- `play-tts-briefing.sh`가 `.claude`에서 `CLAUDE_CONFIG_DIR`를 따른다.
- `scripts/install_macos_commands.py --agent claude --update-stop-hook`이 `ask-question-tts.sh`, `play-tts-briefing.sh`도 함께 설치한다.

## 1.21.0 (2026-11-04)

- `tts-config-context.sh`/`.ps1`이 `.gemini`에서도 첫 호출만이 아니라 매 호출마다 `[tts-config]` 설정 통지를 새로 주입한다.

## 1.20.0 (2026-11-04)

- Antigravity CLI(`agy` 1.4.12+)의 `PreInvocation`·`Stop`·`PreToolUse` 훅 계약을 macOS·Windows 스크립트와 샘플(`assets/hooks/antigravity.macos.hooks.json`, `antigravity.windows.hooks.json`)에 반영했다.
- `tts-config-context.sh`/`.ps1`이 `.gemini`에서 첫 호출(`invocationNum=1`)에만 `injectSteps[0].ephemeralMessage`로 `[tts-config]` 줄과 `tts-summary.txt` 작성 경로를 주입하고, 같은 턴의 재호출(`invocationNum>1`)은 `{}`로 건너뛴다.
- `stop-tts.sh`와 `stop-tts.ps1`+`stop-tts-wrapper.ps1`이 `.gemini`의 요약 누락 시 첫 정상 멈춤(`executionNum=1`, `terminationReason=NO_TOOL_CALL`, `fullyIdle=true`)에서 `{"decision": "continue", "reason": "..."}`를 반환해 1회 재작성을 요청한다.
- `ask-question-tts.sh`/`.ps1`이 `agy`의 `ask_question` 도구(`toolCall.args.questions`, 문자열 배열 `options`)를 파싱하고 `{"decision":"allow"}`를 반환한다.
- `scripts/install_macos_commands.py --agent agy --update-stop-hook` 실행 시 `tts-config-context.sh`, `ask-question-tts.sh`, `play-tts-briefing.sh`, `tts-config-set.sh`도 함께 설치한다.

## 1.19.0 (2026-11-03)

- `assets/tts/azure_tts.py`를 speech-toolkit의 `TTS/azure_tts.py` 동봉 사본으로 바꿨다. 429 재시도는 `--retries`로 켤 때만 하고 기본은 0이라 provider의 SAPI 폴백 시점은 그대로다. Windows에서 프로세스 환경에 키가 없으면 사용자 환경 변수에서 읽어 provider 밖에서 직접 불러도 동작한다. 입력 파일을 빼면 현재 폴더의 첫 `.txt`·`.md`를 쓴다.

## 1.17.1 (2026-10-29)

- 정상 요약·공백 억제·현재 턴 발췌가 같은 세션·턴 잠금을 공유해 반복·동시 Stop의 중복 재생을 막는다.

## 1.17.0 (2026-10-29)

- macOS Codex 질문·중간보고에 최종 요약과 같은 provider·음성·속도 설정을 적용한다.
- 계획 모드에서 요약이 없으면 현재 세션·현재 턴 final을 대조해 앞 1~2문장만 한 번 읽는다.
- macOS Codex 요약 누락 시 추가 모델 턴을 요청하지 않으며, API provider 오류는 로그 후 중단한다.
- Codex 명령 설치기에 현재 턴 발췌 helper와 질문·중간보고 스크립트를 포함한다.
