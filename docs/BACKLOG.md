# BACKLOG

아직 하지 않은 것을 둔다. 끝난 항목은 지우고 `CHANGELOG.md`에 남긴다.

## 착수 순서

| 묶음 | 항목 | 필요 환경 | 순서 |
|---|---|---|---|
| macOS 실기 확인 | **Codex·agy 요약 음성 미리 합성 실제 턴 확인** | 로컬 필요·위원장 | 선행 |
| macOS 실기 확인 | **macOS Codex 계획 모드 발췌 청취 확인** | 로컬 필요·위원장 | 병행 |
| macOS 실기 확인 | **macOS Codex API 실패 시 say 폴백 실기 확인** | 로컬 필요·위원장 | 병행 |
| Windows 실기 확인 | **Windows 세션 음소거·/tts-replay 공백 요약 실기 확인** | 로컬 필요·위원장 | 병행 |
| 동시 세션 청취 확인 | **동시 세션 순차 재생 청취 확인** | 로컬 필요·위원장 | 병행 |

## 열림

- [ ] **Codex·agy 요약 음성 미리 합성 실제 턴 확인**: Codex는 `/hooks`에서 `tts-presynth.sh` 훅을 신뢰 승인해야 실행된다. 승인 뒤 API provider로 Codex·agy에서 한 턴씩 돌려 각 홈의 `log/stop-tts.log`에 `TTS 미리 합성본 재생`이 남는지 본다. 설치본과 실제 Azure 경로의 훅 동작은 확인했다.
- [ ] **macOS Codex 계획 모드 발췌 청취 확인**: 요약 없이 끝난 계획 모드 턴에서 현재 턴 final 앞 1~2문장을 "응답 앞부분입니다."와 함께 한 번 읽는지 실제로 듣는다.
- [ ] **macOS Codex API 실패 시 say 폴백 실기 확인**: 키를 비운 세션에서 Codex 턴을 끝내 `log/stop-tts.log`에 `say로 폴백`이 남고 내장 음성으로 들리는지 본다. 단위 시험은 통과한다.
- [ ] **Windows 세션 음소거·/tts-replay 공백 요약 실기 확인**: `TTS_SUMMARY=off` 세션의 무발화와 `/tts-replay` 턴의 공백 요약 통과를 Windows 실기에서 확인한다. `test_*_windows.py`는 PowerShell이 있는 환경에서만 돈다.
- [ ] **동시 세션 순차 재생 청취 확인**: 터미널 두 개에서 같은 CLI(또는 서로 다른 CLI)의 턴을 거의 동시에 끝내 두 요약이 모두, 겹치지 않고 차례로 들리는지 귀로 확인한다. Windows는 세 CLI의 실제 턴에서 세션 전용 파일 통지·소비까지 확인했고 겹침 방지는 단위 시험으로만 확인했다. macOS는 설치본 갱신(`install_macos_commands.py --update-stop-hook`) 뒤 확인한다.

## 판정 대기

착수할지 위원장 판정이 필요한 확장이다. 판정 전에는 착수 순서 표에 넣지 않는다.

- **Windows 질문 안내·중간 보고의 provider 공유**: 지금은 `play-tts-briefing.ps1`이 SAPI 고정이다. macOS는 세 CLI 모두 요약과 같은 provider를 쓴다.
- **Windows 질문 안내·중간 보고의 세션 음소거**: 지금은 `TTS_SUMMARY=off` 세션에서도 들린다. macOS는 따른다.
- **Windows 요약 음성 미리 합성**: macOS의 `tts-presynth.sh`에 해당하는 Windows 판이 없다.
- **Windows 전문 낭독·중지 명령**: `read`·`pause`는 macOS 전용이다.
- **pi의 API provider·전문 낭독·질문 안내**: pi 확장은 내장 음성 요약 재생·누락 보충과 `/tts`·`/tts-replay`·`/tts-pause`를 지원하고, API provider·전문 낭독·질문 안내는 없다.
- **Azure 스트리밍 합성(Speech SDK)**: REST는 전체 합성이 끝난 뒤 한꺼번에 보내 긴 요약일수록 첫소리가 늦다. SDK 스트리밍은 길이와 무관하게 첫소리를 앞당기지만 별도 설치와 Windows 판 수정이 필요하다. 미리 합성 뒤에는 이득이 긴 요약에만 남는다.
