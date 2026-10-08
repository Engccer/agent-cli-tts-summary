# agy TTS 명령 (macOS)

agy의 `tts-read`는 현재 대화의 마지막 완료 응답을 내장 음성으로 읽는다. `tts-replay`는 보관된 최신 요약 음성을 다시 재생한다. `tts-pause`는 agy의 진행 중인 요약·재생·전문 읽기를 종료한다. 중지해도 TTS 켜기 설정은 유지하며 재개 지점은 저장하지 않는다.

## 설치

`~/.gemini/TTS-Summary/tts-config.txt`를 준비한 뒤 저장소에서 실행한다. 설정 파일이 없으면 설치를 중단하며 기본값을 자동 생성하지 않는다.

```bash
python3 scripts/install_macos_commands.py --agent agy --update-stop-hook
```

공통 스크립트와 Python 모듈은 `~/.gemini/hooks/`, 세 스킬은 `~/.gemini/config/skills/`에 설치한다. 설정과 훅 등록은 보존한다. 기존 파일은 `~/.gemini/backups/tts-commands-*`에 백업한다. `--update-stop-hook`을 생략하면 기존 `stop-tts.sh`도 유지한다. 요약 음성까지 중지하려면 갱신한 Stop 실행 파일이 필요하다. 설치 대상이나 백업 경로가 심볼릭 링크면 쓰기 전에 중단한다.

설치 후 agy에서 `/skills reload`를 실행한다. 스킬은 모델이 셸 도구로 명령을 실행하는 방식이다.

```bash
AGENT_DIR_NAME=.gemini bash ~/.gemini/hooks/tts-read.sh
AGENT_DIR_NAME=.gemini bash ~/.gemini/hooks/tts-pause.sh
AGENT_DIR_NAME=.gemini bash ~/.gemini/hooks/tts-replay.sh
```

전문 읽기는 `ANTIGRAVITY_CONVERSATION_ID`에 해당하는 현재 대화만 선택한다. 식별자나 읽을 응답이 없으면 실패를 알리고 다른 대화로 넘어가지 않는다. 코드 블록은 종류만 안내한다. 읽기·재생·중지 턴에는 새 `tts-summary.txt`를 작성하지 않는다.

## 검증

```bash
python3 scripts/test_install_macos_commands.py
```

`TTS_READ_DRYRUN=1`은 전문 선택과 텍스트 변환을, `TTS_REPLAY_DRYRUN=1`은 요약 음성 파일 선택을 확인한다. 실제 음성 재생 증거는 아니다. 이 명령들은 중복 요약 억제용 공백 파일을 만들 수 있으므로 실제 홈에서 조회만 할 때는 `TTS_SUMMARY=off`도 지정한다. 중지는 설치 후 새로 시작한 낭독으로 확인한다.
