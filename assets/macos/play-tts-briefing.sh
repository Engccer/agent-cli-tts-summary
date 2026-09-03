#!/usr/bin/env bash
#
# 긴 작업의 중간 phase 보고를 macOS say로 비동기 재생한다.
# 음성 사용 여부, 응답 완료 전 발화 여부(interim), say 음성, 속도는 TTS-Summary/tts-config.txt 하나에서 읽는다.
# 사용법: bash play-tts-briefing.sh "보고문"
# 검증: BRIEFING_TTS_DRYRUN=1이면 재생하지 않고 voice/rate/text를 출력한다.
#
set +e

AGENT_DIR_NAME="${AGENT_DIR_NAME:-.codex}"   # <-- 이식 시 기본값만 변경
AGENT_DIR="$HOME/$AGENT_DIR_NAME"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/tts-config.sh" 2>/dev/null || exit 0
tts_config_load "$AGENT_DIR"
tts_enabled || exit 0
tts_interim_enabled || exit 0

SPEAK_TEXT="$*"
[ -n "${SPEAK_TEXT//[[:space:]]/}" ] || exit 0
RATE="$(tts_rate_wpm)"

if [ "${BRIEFING_TTS_DRYRUN:-0}" = "1" ]; then
  printf 'voice=%s\nrate=%s\ntext=%s\n' "$TTS_VOICE_SAY" "$RATE" "$SPEAK_TEXT"
  exit 0
fi

SAY_ARGS=()
[ -n "$TTS_VOICE_SAY" ] && SAY_ARGS+=(-v "$TTS_VOICE_SAY")
SAY_ARGS+=(-r "$RATE")
nohup /usr/bin/say "${SAY_ARGS[@]}" -- "$SPEAK_TEXT" >/dev/null 2>&1 &

exit 0
