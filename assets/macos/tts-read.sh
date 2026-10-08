#!/usr/bin/env bash
# 현재 에이전트 세션의 마지막 완료 응답을 내장 음성으로 읽는다.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR_NAME="${AGENT_DIR_NAME:-.claude}"
AGENT_DIR="$HOME/$AGENT_DIR_NAME"
case "$AGENT_DIR_NAME" in
  .claude) AGENT=claude; AGENT_DIR="${CLAUDE_CONFIG_DIR:-$AGENT_DIR}"; SESSION_ID="${1:-${CLAUDE_SESSION_ID:-}}" ;;
  .codex) AGENT=codex; SESSION_ID="${1:-${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-}}}" ;;
  .gemini) AGENT=agy; SESSION_ID="${1:-${ANTIGRAVITY_CONVERSATION_ID:-}}" ;;
  *) echo '지원하지 않는 에이전트입니다.'; exit 1 ;;
esac
. "$SCRIPT_DIR/tts-config.sh"
tts_config_load "$AGENT_DIR"

# /tts-replay와 같은 Stop hook 계약. 오류 안내에도 새 요약이 겹치지 않는다.
if ! tts_session_muted; then
  printf '\n' > "$AGENT_DIR/tts-summary.txt"
fi

python3 "$SCRIPT_DIR/tts-read.py" --agent-dir "$AGENT_DIR" \
  --agent "$AGENT" --session-id "$SESSION_ID" --voice "$TTS_VOICE_SAY" --rate "$(tts_rate_wpm)"
