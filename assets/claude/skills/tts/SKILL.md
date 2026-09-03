---
name: tts
description: TTS 음성 요약을 터미널에서 바로 켜고 끄거나 속도·상세 정도를 바꾼다. 사용자가 /tts를 직접 칠 때만 동작한다.
argument-hint: "[on|off|speed <1~10>|verbosity <1~3>]"
disable-model-invocation: true
---

!`bash ~/.claude/hooks/tts-config-set.sh "$ARGUMENTS"`

위 한 줄이 방금 적용된 TTS 설정이다. 그 줄을 그대로 사용자에게 전달하고 다른 작업은 하지 않는다. 오류 문구가 나왔으면 오류 문구를 전달한다.
