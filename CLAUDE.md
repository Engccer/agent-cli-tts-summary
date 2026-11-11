# CLAUDE.md

agent-cli-tts-summary: Claude Code·Codex CLI·Antigravity CLI(`agy`)·pi의 턴 요약을 음성으로 읽어 주는 훅·스크립트 모음이자 자작 스킬이다. 현재 행동의 정본은 `SKILL.md`와 `references/*.md`, 현재 상태는 `PROGRESS.md`, 남은 일은 `docs/BACKLOG.md`다.

## 항구 규칙

- **`assets/`는 템플릿이고 실제로 도는 것은 각 에이전트 홈의 설치 사본이다.** 훅 스크립트의 `AGENT_DIR_NAME` 기본값(`.codex` 또는 `.claude`)은 설치기가 대상 폴더명으로 바꾼다. provider 스크립트(`play-tts-*-api.sh`)의 고정 `AGENT_DIR_NAME`과 `CONVERTER_SCRIPT`의 `<SKILL_DIR>`는 설치기가 다루지 않으므로 손으로 치환해 복사한다. `assets/`를 고친 뒤 이 Mac에 반영하려면 `python3 scripts/install_macos_commands.py --agent <claude|codex|agy> --update-stop-hook`으로 다시 설치하거나 같은 치환으로 복사하고, 설치본과 `diff`해 확인한다. 저장소만 고치면 동작은 바뀌지 않는다.
- **macOS와 Windows는 같은 계층을 두 벌 둔다**(`assets/macos/*.sh` ↔ `assets/windows/*.ps1`). 한쪽 동작을 바꾸면 다른 쪽에 같은 변경이 필요한지 판정하고, 하지 않으면 `docs/BACKLOG.md`에 남긴다. 문서에서 심볼 실재를 확인할 때도 그 문장이 말하는 폴더로 좁혀 grep한다.
- **세 CLI의 훅 계약은 다르다.** matcher 도구명(Claude `AskUserQuestion`·`Write|Edit|MultiEdit`, Codex `request_user_input`·`^apply_patch$`, agy `ask_question`·`write_file|edit_file`), payload 모양, stdout·종료 코드 규약(agy는 모든 이벤트에서 JSON 필수, Codex `UserPromptSubmit`은 `hookSpecificOutput` JSON, Windows Codex 누락 가드는 `exit 2`, macOS Codex Stop은 `exit 2`를 쓰지 않음)이 각각 다르다. 새 훅은 `references/macos.md`의 에이전트별 절을 먼저 읽고 붙인다. Codex는 새 훅이나 내용이 바뀐 훅을 `/hooks`에서 신뢰 승인해야 실행한다.
- **훅은 CLI를 막거나 늦추면 안 된다.** 합성·재생은 `tts_playback.py run --launchd`의 일회성 launchd 작업으로 떼어 내고 훅의 stdout·stderr 파이프를 물지 않게 한다. CLI는 훅 자손을 정리하거나 파이프 EOF를 기다리므로 `&` 백그라운드만으로는 안전하지 않다.
- **API provider가 실패하면 언제나 내장 음성으로 폴백한다.** 요약이 들리지 않는 실패는 허용하지 않는다.
- **시험은 소리·네트워크·launchd에 닿지 않게 한다.** `scripts/test_*.py`는 재생 경로에 닿지 않는 분기, 가짜 provider·`afplay`, 필요하면 `sandbox-exec`(네트워크·`say`·`afplay`·`launchctl` 차단)로 소리·네트워크·launchd를 막는다. 기능·버그 수정은 같은 커밋에 시험을 동반하고 `for t in scripts/test_*.py; do python3 "$t"; done`과 `node --test scripts/test_pi_extension.mjs`로 전체를 돌린다. 실기 확인이 필요하면 `TTS_SUMMARY=off`로 띄운 세션이나 임시 HOME을 쓴다.
- **스킬 문서(`SKILL.md`·`references/`)에는 현재 행동만 쓴다.** 날짜 붙은 경위·사고 서사는 `CHANGELOG.md`와 커밋 메시지에 둔다.
- **버전은 `SKILL.md` frontmatter `version`이 정본이다.** 동작 변경은 minor, 표현 수정은 patch를 올리고 `CHANGELOG.md`에 같은 번호로 적는다.
- **공개 저장소다.** 커밋 전 개인 흔적 검사(sanitize-for-release)가 0건인지 확인한다. 허용 목록 `.sanitize.local.md`는 추적하지 않는 로컬 파일이다.

## 커밋·푸시

자작 스킬 저장소라 수정한 턴에 commit·push까지 마친다. main 직접 커밋이며 원격은 `Engccer/agent-cli-tts-summary`다.
