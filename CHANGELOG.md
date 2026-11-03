# 변경 기록

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
