---
name: tts-replay
description: 직전 턴의 TTS 요약 음성 파일을 한 번 더 재생한다. 사용자가 /tts-replay를 직접 칠 때만 동작한다.
disable-model-invocation: true
---

!`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$USERPROFILE\.claude\hooks-windows\tts-replay.ps1"`

위 한 줄을 그대로 사용자에게 전달하고 다른 작업은 하지 않는다. 이 턴에는 tts-summary.txt를 쓰지 않는다. 재생 스크립트가 이 턴의 요약 자리를 이미 비워 두었고, 새 요약을 쓰면 재생 중인 음성 위에 겹쳐 읽힌다.
