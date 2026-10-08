# Codex TTS 명령 (macOS)

Codex에서는 `/skills` 메뉴로 설정과 재생 스킬을 선택한다. 직접 입력은 `$codex-tts`, `$codex-tts-replay`, `$codex-tts-read`, `$codex-tts-pause`다. Claude용 자산과 이름을 구분해 다른 에이전트의 설정을 바꾸는 일을 막는다.

| 기능 | Codex 입력 |
|---|---|
| 현재 설정 | `$codex-tts` |
| 켜기·끄기 | `$codex-tts on`, `$codex-tts off` |
| 속도 | `$codex-tts speed 8` |
| 상세 정도 | `$codex-tts verbosity 2` |
| 선택지·중간 보고 | `$codex-tts interim off` |
| 직전 요약 다시 듣기 | `$codex-tts-replay` |
| 마지막 완료 응답 전문 읽기 | `$codex-tts-read` |
| 현재 낭독 중지 | `$codex-tts-pause` |

Codex CLI 0.153.4에서 `/tts` 직접 입력은 `Unrecognized command`로 거부된다. 이 설치는 Codex 바이너리에 슬래시 별칭을 추가하지 않는다. 스킬은 모델이 셸 도구를 호출하는 방식이며, 실제 설정 변경과 파일 선택은 기존 스크립트가 수행한다. Claude의 `!` 전처리처럼 모델을 거치지 않는 실행으로 설명하지 않는다. 공식 호출 규약: [OpenAI 스킬 문서](https://developers.openai.com/codex/skills).

## 설치

기본 TTS 루프를 설치한 뒤 스킬 저장소에서 실행한다. 표준 홈 경로 `~/.codex`를 대상으로 하며, 별도 `CODEX_HOME` 구성과 Windows 명령 설치는 이 설치기의 지원 범위에 포함되지 않는다.

```bash
python3 scripts/install_codex_commands.py
```

- `~/.codex/hooks-macos/`에 설정기, 재생기, 전문 읽기와 중지 스크립트 및 공통 Python 모듈을 설치한다.
- `~/.codex/skills/`에 `codex-tts`, `codex-tts-replay`, `codex-tts-read`, `codex-tts-pause`를 설치한다.
- `TTS-Summary/tts-config.txt`와 훅 등록은 보존한다. 기존 명령 파일은 `~/.codex/backups/tts-commands-*`에 백업한 뒤 갱신한다. 설치 대상이나 백업 경로가 심볼릭 링크면 쓰기 전에 중단한다.
- 기존 요약의 중지까지 지원하려면 다음 명령으로 Stop 실행 파일도 갱신한다. 훅 등록은 그대로 둔다.

```bash
python3 scripts/install_macos_commands.py --agent codex --update-stop-hook
```

전문 읽기는 현재 `CODEX_THREAD_ID`를 우선하며 없으면 `CODEX_SESSION_ID`를 사용한다. 마지막 완료 응답을 내장 음성으로 읽고 코드 블록은 종류만 안내한다. 식별자가 없거나 응답을 찾지 못하면 실패를 알린다. 다른 대화로 넘어가지 않는다. 읽기·재생·중지 턴에는 새 요약을 작성하지 않는다.

중지는 해당 에이전트의 현재 요약·재생·전문 읽기를 종료한다. 재개 지점은 저장하지 않으며 TTS 켜기 설정은 유지한다. 기존 방식으로 이미 시작한 낭독은 새 관리 상태에 등록되지 않을 수 있으므로 설치 후 새로 시작한 낭독으로 검증한다.

템플릿은 `assets/codex/*/SKILL.md.in`이다. 설치 전 자산이 실행 가능한 스킬로 잘못 검색되지 않도록 `.in` 확장자를 유지한다.

## 검증

```bash
python3 scripts/test_install_codex_commands.py
bash ~/.codex/hooks-macos/tts-config-set.sh
```

새 Codex 세션에서 `/skills`로 네 이름이 보이는지 확인하고 `$codex-tts`로 실제 설정기 호출과 출력까지 확인한다. 목록에만 보인다고 동작 성공으로 판정하지 않는다. 설정 변경은 즉시 반영되며 명령 목록이 갱신되지 않을 때만 세션을 다시 시작한다.

재생 검증은 `TTS_REPLAY_DRYRUN=1`로 파일 선택만 확인할 수 있다. 이 모드도 공백 요약 파일을 만들므로 실제 홈을 조회만 하려면 `TTS_SUMMARY=off`를 함께 지정한다. 출력은 실제 재생 증거가 아니다. TTS를 끈 사용자의 설정을 검증 목적으로 켜지 않는다.
