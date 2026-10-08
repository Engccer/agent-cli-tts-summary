#!/usr/bin/env bash
# /tts-read: 현재 Claude 세션의 마지막 완료 응답을 내장 음성으로 읽는다.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
. "$SCRIPT_DIR/tts-config.sh"
tts_config_load "$AGENT_DIR"

# /tts-replay와 같은 Stop hook 계약. 오류 안내에도 새 요약이 겹치지 않는다.
if ! tts_session_muted; then
  printf '\n' > "$AGENT_DIR/tts-summary.txt"
fi

python3 "$SCRIPT_DIR/tts-read.py" --agent-dir "$AGENT_DIR" \
  --session-id "${1:-}" --voice "$TTS_VOICE_SAY" --rate "$(tts_rate_wpm)"
