---
name: tts-read
description: 현재 Claude 대화의 마지막 완료 응답 전문을 읽는다. 사용자가 /tts-read를 직접 칠 때만 실행한다. 코드 블록은 종류만 안내하고 TTS 요약은 읽지 않는다.
disable-model-invocation: true
metadata:
  version: "1.0.0"
---

!`bash ~/.claude/hooks/tts-read.sh "${CLAUDE_SESSION_ID}"`

위 실행 결과 한 줄만 사용자에게 전달한다. 본문을 다시 작성하거나 요약하지 않는다. 이 턴에는 tts-summary.txt를 쓰지 않는다. 재생기가 공백 요약 파일을 준비했으므로 Stop hook은 새 요약을 읽지 않는다.
