#!/usr/bin/env bash
#
# Stop hook (macOS) - 에이전트가 쓴 tts-summary.txt를 읽어 say로 재생하고 보관한다.
#
# 이식 방법: AGENT_DIR_NAME 한 줄만 대상 에이전트 폴더명으로 바꾼다(.claude/.codex/.gemini).
# 음성은 에이전트 홈의 tts-voice-say.txt(예: "Yuna (Premium)")로, 속도는 tts-rate-wpm.txt로 제어한다.
# 실패해도 CLI 턴을 깨지 않도록 항상 exit 0으로 끝낸다.
#
set +e

AGENT_DIR_NAME=".codex"   # <-- 이식 시 이 한 줄만 변경

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
SUMMARY_FILE="$AGENT_DIR/tts-summary.txt"
TXT_DIR="$AGENT_DIR/TTS-Summary/txt"
WAV_DIR="$AGENT_DIR/TTS-Summary/wav"
VOICE_FILE="$AGENT_DIR/tts-voice-say.txt"
RATE_FILE="$AGENT_DIR/tts-rate-wpm.txt"
MAX_FILES=10

[ -s "$SUMMARY_FILE" ] || exit 0

SUMMARY="$(cat "$SUMMARY_FILE")"
rm -f "$SUMMARY_FILE"
[ -n "$SUMMARY" ] || exit 0

mkdir -p "$TXT_DIR" "$WAV_DIR"
TS="$(date +%Y%m%d-%H%M%S)"

# TXT 보관
printf '%s\n' "$SUMMARY" > "$TXT_DIR/summary-$TS.txt"

# 음성/속도 옵션 구성
SAY_ARGS=()
if [ -s "$VOICE_FILE" ]; then
  SAY_ARGS+=(-v "$(cat "$VOICE_FILE")")
fi
if [ -s "$RATE_FILE" ]; then
  SAY_ARGS+=(-r "$(cat "$RATE_FILE")")
fi

# AIFF로 저장 후 WAV로 변환(afconvert는 macOS 기본 제공). 변환 실패해도 재생은 진행.
AIFF="$WAV_DIR/tts-$TS.aiff"
WAV="$WAV_DIR/tts-$TS.wav"
say "${SAY_ARGS[@]}" -o "$AIFF" "$SUMMARY" 2>/dev/null
if [ -f "$AIFF" ]; then
  afconvert "$AIFF" "$WAV" -d LEI16 -f WAVE 2>/dev/null && rm -f "$AIFF"
fi

# 재생(파일이 있으면 파일을, 없으면 say 직접 재생)
if [ -f "$WAV" ]; then
  afplay "$WAV" 2>/dev/null
elif [ -f "$AIFF" ]; then
  afplay "$AIFF" 2>/dev/null
else
  say "${SAY_ARGS[@]}" "$SUMMARY" 2>/dev/null
fi

# 최신 MAX_FILES개만 유지
ls -1t "$TXT_DIR"/summary-*.txt 2>/dev/null | tail -n +$((MAX_FILES + 1)) | xargs -I {} rm -f {}
ls -1t "$WAV_DIR"/tts-*.wav      2>/dev/null | tail -n +$((MAX_FILES + 1)) | xargs -I {} rm -f {}

exit 0
