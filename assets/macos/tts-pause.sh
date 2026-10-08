#!/usr/bin/env bash
# 재생 중인 해당 에이전트의 TTS 작업만 종료한다. 재개 지점은 저장하지 않는다.
set -eu
AGENT_DIR_NAME="${AGENT_DIR_NAME:-.claude}"
AGENT_DIR="$HOME/$AGENT_DIR_NAME"
[ "$AGENT_DIR_NAME" != ".claude" ] || AGENT_DIR="${CLAUDE_CONFIG_DIR:-$AGENT_DIR}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/tts-config.sh"
if ! tts_session_muted; then
  printf '\n' > "$AGENT_DIR/tts-summary.txt"
fi
python3 "$SCRIPT_DIR/tts_playback.py" pause --agent-dir "$AGENT_DIR"
tts_mark_control_turn
