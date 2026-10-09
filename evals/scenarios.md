# 시험 시나리오와 채점 항목

스킬 감사(skill-audit)의 개정 전후 시험에 쓴다. 시험자에게는 시나리오만 주고 채점 항목은 주지 않는다. T1~T4는 한 시험자, T5(평범한 하루)는 별도 시험자가 푼다.

## T1. Windows 새 PC에 Claude Code 루프 설치, 영어 요약

> 새 Windows PC(PowerShell 5.1, 기본 SAPI 음성)에 Claude Code만 쓴다. 요약은 영어로 듣고 싶고, 질문 선택지도 소리로 읽어 주면 좋겠다. `~/.claude/TTS-Summary/tts-config.txt`는 예전에 한 번 만들어 둔 것이 이미 있다. 무엇을 어떤 순서로 설치·설정하나?

채점 항목:
1. 요약 언어는 글로벌 지침 블록 생성 단계에서 `render_instruction_block.py --language English`(또는 그에 준하는 영어 지정)로 반영한다.
2. 설정 파일의 음성·언어 항목(`voice_sapi`를 영어 음성으로, `language_code`를 `en-US`)도 함께 바꾼다.
3. 기존 `tts-config.txt`를 덮어쓰지 않는다.
4. 질문 선택지 안내를 원하므로 `interim=on`으로 바꾼다(Windows 기본은 `off`)와 `ask-question-tts.ps1` PreToolUse 등록(matcher `AskUserQuestion`).
5. `/tts`: `tts-config-set.ps1`을 `hooks-windows`에, `SKILL.windows.md`를 `~/.claude/skills/tts/SKILL.md`로 이름 바꿔 복사하고 `$USERPROFILE` 확장을 첫 설치 때 확인한다.
6. `.ps1`은 UTF-8 with BOM을 보존해 복사한다.
7. Stop hook timeout은 300.

## T2. 병렬 세션에서 작업 세션만 음소거 (macOS)

> Mac Claude Code에서 코디네이터 세션 1개와 작업 세션 3개를 동시에 띄운다. 코디네이터 창의 요약만 들리고 작업 세션 3개는 조용했으면 한다. 어떻게 하나? 작업 세션의 Stop hook은 그때 무엇을 하나?

채점 항목:
1. 작업 세션을 환경 변수 `TTS_SUMMARY=off`로 띄운다(`parallel-sessions` 런처가 심는다).
2. `/tts off`나 설정 파일 `enabled=off`는 에이전트 홈 전체를 끄므로 쓰지 않는다.
3. 세션 ID 기반 덮어쓰기 계층 같은 새 설계를 제안하지 않는다(낡은 조치).
4. 음소거 세션의 Stop hook은 가드도 재생도 하지 않고, 남은 `tts-summary.txt`를 지우지 않는다(코디네이터 것일 수 있다).
5. 음소거 세션에는 설정 통지 훅이 매 턴 끔 사실과 보고 경로(코디네이터)를 알리고, 작업 세션은 요약 파일을 쓰지 않는다.

## T3. `/tts`로 끄고 켜기, 상세 정도 3, 끊기는 음성 (macOS)

> Mac Claude Code 사용자가 (가) `/tts off`를 쳤다. 이 턴의 응답은 소리가 나나? 직전에 남아 있던 `tts-summary.txt`는 어떻게 되나? (나) 다음 날 `/tts on`과 `/tts verbosity 3`을 쳤다. 요약은 몇 문장으로, 언제부터 바뀌나? (다) 그 뒤 긴 요약이 끝부분에서 뚝 끊긴다고 한다. 무엇을 확인하나?

채점 항목:
1. `/tts off`는 그 턴의 재생부터 꺼진다(Stop hook이 매 턴 설정을 새로 읽는다).
2. 끔 상태의 Stop hook은 남은 `tts-summary.txt`를 지우고 끝낸다(재생·보관·가드 없음).
3. 3단계는 "7문장 이상(근거·트레이드오프·후속 과제)"이다.
4. 상세 정도는 다음 턴의 설정 통지부터 반영된다(통지는 턴 시작에 나가므로 `/tts`를 친 그 턴에는 옛 값). 켬/끔·속도는 같은 턴 재생부터.
5. 끊김: 보관된 요약과 WAV 길이를 비교해 합성 누락과 재생 중단을 구분하고, `log/tts-playback.log`와 해당 provider 로그를 확인한다.
6. 현재 macOS Stop hook은 `tts_playback.py`의 일회성 launchd 작업으로 합성·재생을 넘긴다. 훅 제한 시간은 누락 가드·작업 등록에 적용되며 전체 낭독 시간을 기준으로 늘리지 않는다. 오래된 동기 훅이면 백업 후 `--update-stop-hook`으로 갱신한다.

## T4. Mac의 Antigravity(`agy`)에 루프 붙이기

> Mac에 `agy`(Antigravity CLI)가 설치돼 있다. Claude Code처럼 TTS 요약을 agy에도 붙여 달라. 무엇을 쓰고 어디에 등록하나? 무엇이 안 되나?

채점 항목:
1. macOS용 Gemini/Antigravity 훅 샘플은 없다는 것을 알고, Windows 샘플을 bash로 바꿔 그대로 붙이지 않는다.
2. 등록 자리는 `~/.gemini/config/hooks.json`의 이름 붙인 그룹 스키마, 이벤트는 `Stop`.
3. UserPromptSubmit·PreToolUse가 발동하지 않아 설정 통지(상세 정도 자동 반영)와 질문 선택지 안내를 쓸 수 없다. 분량은 `GEMINI.md` 지침 문구로 고정한다.
4. `AGENT_DIR_NAME=.gemini`, 요약·보관 경로는 `.gemini` 아래.
5. macOS `stop-tts.sh`는 일회성 launchd 작업에 합성·재생을 맡기고 반환한다. `tts_playback.py`를 함께 설치한다.
6. 등록 뒤 실제로 Stop 이벤트가 발동하는지 확인한다.

## T5. 평범한 하루: 속도 올리고 다시 듣기 (macOS, 별도 시험자)

> Mac Claude Code에 루프가 정상 설치돼 있다. 사용자: "요약 읽는 속도 좀 빠르게, 7.5로 해 줘. 그리고 방금 요약 한 번만 더 들려줘."

채점 항목:
1. 속도: 사용자가 `/tts speed 7.5`를 치게 안내하거나(모델이 스스로 호출할 수 없는 명령), 설정 파일 `speed=7.5`를 고치거나, 설정기 `tts-config-set.sh speed 7.5`를 실행한다. 소수점 허용.
2. 다음 재생부터(같은 턴 Stop 재생부터) 적용되고 세션 재시작이 필요 없다.
3. 다시 듣기는 `/tts-replay`(사용자가 친다). 새로 합성하지 않고 최신 WAV를 튼다(API provider여도 비용 없음).
4. `/tts-replay` 턴에는 새 요약을 쓰지 않는다(겹침 방지).
5. 참고 문서(`references/`)를 열 필요가 없다(읽은 파일 목록으로 확인).

## T6. 세 도구의 전문 읽기와 중지 (macOS)

> Claude Code·Codex·agy에서 마지막 응답을 요약 없이 그대로 듣고 싶다. 응답에는 목록, Python 코드 블록, 마지막 설명 문장이 있다. 낭독을 중간에 멈추고 다시 전문 읽기를 실행한 다음, 새 질문의 요약은 계속 듣고 싶다. 무엇을 설치하고 어떻게 검증하나?

채점 항목:
1. 각 도구의 기존 설정과 훅 등록을 보존하며 `install_macos_commands.py --agent <도구> --update-stop-hook`으로 설치한다. Python 3와 `markdown-it-py` 3.x 또는 4.x를 확인한다.
2. Claude·agy는 `/tts-read`·`/tts-pause`, Codex는 `$codex-tts-read`·`$codex-tts-pause`를 사용한다.
3. 현재 세션의 마지막 완료 응답을 선택하고 목록과 마지막 문장을 보존한다. 코드 본문은 종류 안내로 바꾸며 도구 결과·TTS 요약 파일은 읽지 않는다.
4. 연속 명령의 확인 응답을 다음 전문 읽기의 대상으로 선택하지 않는다. 명령 턴에 새 요약을 쓰지 않는다.
5. 중지는 해당 에이전트의 등록된 작업만 종료하며 자동 요약 설정을 유지한다. 전문 읽기를 다시 실행하면 처음부터 읽는다.
6. 요약·replay·read 각각의 중지를 확인한다. dry-run 출력은 텍스트·파일 선택 검증이며 실제 재생·중지의 증거로 대신하지 않는다.
