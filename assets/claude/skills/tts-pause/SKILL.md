---
name: tts-pause
description: 현재 Claude의 요약, replay, read 낭독과 질문 안내·중간 보고·미리 합성 작업을 중지한다. 사용자가 /tts-pause를 직접 입력할 때 실행한다.
disable-model-invocation: true
metadata:
  version: "1.0.1"
---

!`bash ~/.claude/hooks/tts-pause.sh "${CLAUDE_SESSION_ID}"`

위 결과 한 줄만 전달한다. 현재 낭독을 종료하는 명령이며 재개 지점은 저장하지 않는다. 이 턴에는 요약 파일을 작성하지 않는다. 중지 스크립트가 새 요약 낭독을 억제하는 공백 파일을 준비했다.
