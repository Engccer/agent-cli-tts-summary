# pi 음성 요약 (macOS)

pi 1.1.0 이상에서 응답 완료 후 한국어 요약을 macOS 내장 음성으로 읽는다. 로컬 모델도 파일 작성 도구를 사용할 수 있으면 같은 방식으로 동작한다. 설치된 버전은 `pi --version`, 사용 가능한 모델은 `pi --list-models`로 확인한다.

## 설치와 설정

저장소 루트에서 실행한다.

```bash
python3 scripts/install_pi_tts.py
```

Python 3.9 이상, Node.js 기반 pi, macOS 내장 `say`·`afconvert`·`afplay`·`launchctl`이 필요하다. 설치기는 `~/.pi/agent/extensions/tts-summary.ts`와 `~/.pi/agent/hooks/`에 확장과 공용 스크립트를 복사한다. 기존 모델·pi 설정과 `TTS-Summary/tts-config.txt`를 보존하며, 교체하는 실행 파일은 `backups/pi-tts-*`에 먼저 백업한다. 같은 내용으로 재설치하면 변경하지 않는다.

`PI_CODING_AGENT_DIR`를 쓰면 설치할 때와 pi를 실행할 때 같은 값을 지정한다. 설치기의 `--agent-dir`로도 지정할 수 있다. `--home`은 격리된 테스트 홈을 만드는 용도다.

새 pi 세션 또는 `/reload`로 확장을 불러온다. 이후 설정 변경은 재시작 없이 적용된다. 음성 이름은 `say -v '?'`에서 확인해 pi 홈의 `TTS-Summary/tts-config.txt`에 `voice_say=음성 이름`으로 넣는다. 이 설치기는 무료 내장 음성(`provider=say`)에 필요한 파일을 설치한다.

| 명령 | 동작 |
| --- | --- |
| `/tts` | 현재 설정 표시 |
| `/tts on`, `/tts off` | 자동 음성 요약 켜기·끄기 |
| `/tts speed 7.5` | 속도 변경(1~10, 소수점 허용) |
| `/tts verbosity 2` | 요약 분량 변경(1: 1~2문장, 2: 3~6문장, 3: 7문장 이상) |
| `/tts-replay` | 직전 요약 음성을 재합성 없이 다시 재생 |
| `/tts-pause` | pi의 현재 낭독 중지 |

명령은 모델을 호출하지 않는다. 명시적으로 요청한 replay는 자동 요약이 꺼져 있어도 실행된다. pause는 다음 응답의 자동 요약 설정을 바꾸지 않는다. 보관과 중지의 범위는 pi 홈 전체이며, 자동 요약용 임시 파일은 요청별로 격리된다. 전문 읽기와 질문 선택지·중간 보고의 자동 낭독은 pi 확장에 포함하지 않는다.

## 동작 계약

- `before_agent_start`: 공용 설정 통지 스크립트를 읽고 한국어 요약 지시를 해당 요청의 시스템 지침에 추가한다. 요청별 `TTS-Summary/pending/turn-*/tts-summary.txt` 경로를 전달한다. 파일 작성 도구를 활성화해야 한다.
- `agent_before_settle`: 최종 outcome을 보관한다. 정상 완료인데 요약이 비어 있으면 숨김 `custom_message`를 추가하고 한 번만 이어서 작성하도록 요청한다. 기존 `event.entries`를 보존한다. 메시지를 추가하기 전 `context.canContinue`는 false일 수 있으므로 선행 조건으로 쓰지 않는다.
- `agent_settled`: 중단되지 않았고 마지막 outcome이 completed인 경우에만 요약을 재생한다. 이벤트 자체에는 error outcome이 없으므로 앞 이벤트에서 보관한 값을 사용한다. 파일 내용은 셸 명령에 삽입하지 않고 `tts_playback.py run --launchd`의 stdin으로 전달한다. 작업자는 공용 `stop-tts.sh --speak`를 실행한다.
- 설정은 시작·보충·재생 직전에 다시 확인한다. `enabled=off` 또는 세션 환경의 `TTS_SUMMARY=off`면 자동 재생하지 않는다. 두 번 누락하면 경고하고 넘어가며 계속 재요청하지 않는다.
- 임시 파일은 최종 처리·세션 종료 때 삭제한다. 성공한 요약의 TXT/WAV는 pi 홈 아래 각각 최신 10개를 보관한다. 강제 프로세스 종료로 남은 pending 파일은 다음 요청에서 재사용하지 않는다.

## 검증

```bash
python3 scripts/test_install_pi_tts.py
node --test scripts/test_pi_extension.mjs
```

확장 테스트는 설치된 pi의 jiti를 사용하고, 임시 홈에서 실제 설정 스크립트와 재생 대역을 실행한다. 정상 완료 한 번 재생, 누락 보충 1회, 취소·오류·off·세션 음소거, 요청별 경로 격리, 명령 실행과 정리를 확인한다.

실제 선택 모델로도 짧은 응답을 발생시킨다. 모델이 바뀌면 요약 작성 지시를 따르는지 다시 확인한다. 로컬 glimmer를 `local/glimmer`로 등록했다면 다음처럼 시험할 수 있다.

```bash
pi --offline --no-context-files --no-skills --no-prompt-templates --no-mcp \
  --provider local --model glimmer --tools write --no-session --print \
  '파일 백업이 무엇인지 초보자에게 쉽게 알려 줘.'
```

TXT에 답의 핵심이 직접 담겼는지, WAV가 생성됐는지, 재생 작업 종료 후 `TTS-Summary/playback/jobs.json`이 비었는지, `log/tts-playback.log`에 오류가 없는지 확인한다. 파일과 프로세스 검증은 사용자가 실제로 소리를 들었다는 확인과 구분한다. `/tts`, `/tts-replay`, `/tts-pause`도 실제 pi에서 실행한다. `python3 scripts/inspect_tts_loop.py --root "$HOME"`로 설정·보관 상태를 확인할 수 있다(기본 pi 홈 기준).

API 근거: [pi 확장 문서](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md), [이벤트 타입](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/extensions/types.ts).
