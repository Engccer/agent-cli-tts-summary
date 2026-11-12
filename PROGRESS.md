# 진행 상태

버전 정본은 `SKILL.md` frontmatter `version`이다. 날짜별 변경은 `CHANGELOG.md`, 남은 일은 `docs/BACKLOG.md`에 있다.

## 지금 동작하는 것

- **macOS(Claude Code·Codex CLI·agy)**: 세 CLI가 같은 Stop 훅과 설정 파일(`TTS-Summary/tts-config.txt`)을 쓴다. provider는 `say`·Gemini·ElevenLabs·Azure이며, API가 실패하면 세 CLI 모두 `say`로 폴백한다. 질문 선택지 안내와 중간 보고도 요약과 같은 provider·음성·속도로 읽고 세션 음소거(`TTS_SUMMARY=off`)를 따른다. 전문 낭독(`read`)·다시 듣기(`replay`)·중지(`pause`) 명령이 있다.
- **요약 음성 미리 합성(macOS 세 CLI, API provider)**: 요약 파일을 쓰는 순간 파일 쓰기 훅이 합성해 두고 Stop 훅은 꺼내 재생한다. 이 Mac의 Claude에서는 실측상 응답 완료 뒤 대기가 Azure 합성 0.2~1초에서 0.07초로 줄었다. Codex·agy는 설치본과 실제 Azure 경로로 확인했고, 실제 턴 확인은 남아 있다.
- **macOS Codex 요약 누락**: 추가 모델 턴을 요청하지 않고, 계획 모드에서만 현재 턴 final의 앞 1~2문장을 한 번 읽는다.
- **Windows(Claude Code·Codex CLI·agy)**: Stop 훅·설정 통지·질문 안내·API provider와 SAPI 폴백이 동작한다. 질문 안내·중간 보고는 SAPI 고정이며 세션 음소거를 따르지 않는다.
- **동시 세션**: 세션 전용 요약 파일과 재생 대기열로, 여러 세션·여러 CLI를 동시에 돌려도 요약이 사라지지 않고 먼저 끝난 턴부터 차례로 들린다(`references/architecture.md` "동시 세션"). Windows는 이 PC의 세 CLI 실제 턴에서 세션 경로 통지·소비를 확인했고, macOS는 시험으로만 확인했으며 설치본 갱신이 남아 있다.
- **pi(macOS)**: 내장 음성(`say`) 전용 확장으로 요약 재생·누락 보충 1회와 `/tts`·`/tts-replay`·`/tts-pause`를 지원한다.

## 시험

`for t in scripts/test_*.py; do python3 "$t"; done`과 `node --test scripts/test_pi_extension.mjs`로 전체를 돌린다. `*_windows.py`는 PowerShell이 없으면 건너뛴다.

## 다음 단계

- Codex에서 `/hooks`로 미리 합성 훅을 신뢰 승인한 뒤 Codex·agy의 실제 턴에서 `log/stop-tts.log`의 `TTS 미리 합성본 재생`을 확인한다(`docs/BACKLOG.md`).
- macOS 세 CLI의 설치본을 `install_macos_commands.py --update-stop-hook`으로 갱신하고, 두 세션을 동시에 끝내 순차 재생을 귀로 확인한다(`docs/BACKLOG.md`).

## 알려진 한계

- 재생 순서는 요약을 쓴 시각이 아니라 턴이 끝난 시각을 따르고, 셋 이상이 함께 기다릴 때의 선착순은 운영체제 잠금이 보장하지 않는다.
- Windows Claude·Codex는 Stop hook 안에서 차례를 기다리므로 대기와 재생이 훅 timeout(300초)을 넘으면 그 요약은 끊긴다.

- 셸 명령으로 요약 파일을 쓴 턴은 파일 쓰기 훅이 걸리지 않아 미리 합성 없이 평소대로 합성한다.
- Windows 동작의 실기 확인은 이 Mac에서 할 수 없다. Windows 전용 시험은 PowerShell이 있는 환경에서만 돈다.
