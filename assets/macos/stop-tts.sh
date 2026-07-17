#!/usr/bin/env bash
#
# Stop hook (macOS) - 에이전트가 쓴 tts-summary.txt를 읽어 음성으로 재생하고 보관한다.
#
# 이식 방법: AGENT_DIR_NAME 한 줄만 대상 에이전트 폴더명으로 바꾼다(.claude/.codex/.gemini).
# 재생 provider는 에이전트 홈의 tts-provider.txt로 고른다(모든 에이전트 공통):
#   say(기본) / gemini-api / elevenlabs-api
# provider 스크립트는 이 파일과 같은 폴더에서 찾고, API provider가 실패하면
# 내장 say로 런타임 폴백해 요약이 항상 들리게 한다.
# say 음성은 에이전트 홈의 tts-voice-say.txt(예: "Yuna (Premium)")로, 속도는 tts-rate-wpm.txt로 제어한다.
# 정상 경로는 항상 exit 0으로 끝내 CLI 턴을 깨지 않는다.
#
# 요약 누락 가드: 에이전트가 tts-summary.txt를 쓰지 않고 턴을 끝내면, 아직 한 번도
# 되돌려보내지 않은 경우에 한해 exit 2로 응답을 차단하고 요약 작성을 요구한다. Stop hook
# payload(stdin)의 stop_hook_active가 true면 이미 한 번 재요청한 것이므로 무한루프를 피해 통과한다.
#
set +e

AGENT_DIR_NAME=".codex"   # <-- 이식 시 이 한 줄만 변경

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
SUMMARY_FILE="$AGENT_DIR/tts-summary.txt"
TXT_DIR="$AGENT_DIR/TTS-Summary/txt"
WAV_DIR="$AGENT_DIR/TTS-Summary/wav"
PROVIDER_FILE="$AGENT_DIR/tts-provider.txt"
VOICE_FILE="$AGENT_DIR/tts-voice-say.txt"
RATE_FILE="$AGENT_DIR/tts-rate-wpm.txt"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAX_FILES=10

# --- 요약 누락 가드 ---
# Stop hook payload(stdin)에서 stop_hook_active를 읽어 무한루프를 방지한다.
HOOK_INPUT="$(cat 2>/dev/null)"
STOP_ACTIVE=false
printf '%s' "$HOOK_INPUT" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true' && STOP_ACTIVE=true

if [ ! -s "$SUMMARY_FILE" ]; then
  if [ "$STOP_ACTIVE" != "true" ]; then
    # 아직 한 번도 돌려보내지 않았으면 응답을 차단하고 TTS 요약 작성을 요구한다.
    # 요약 언어는 글로벌 지침의 TTS 요약 규칙이 정하므로 여기서는 특정 언어를 강제하지 않는다.
    echo "TTS 요약 누락: 글로벌 지침(CLAUDE.md/AGENTS.md/GEMINI.md)의 TTS 요약 규칙에 따라(지정된 요약 언어 포함) 이번 응답의 요약을 $SUMMARY_FILE 에 파일 편집 도구로 작성한 뒤 응답을 마치세요." >&2
    exit 2
  fi
  # 이미 한 번 재요청했는데도 비어 있으면 무한루프 방지를 위해 통과한다.
  exit 0
fi

SUMMARY="$(cat "$SUMMARY_FILE")"
rm -f "$SUMMARY_FILE"
[ -n "${SUMMARY//[[:space:]]/}" ] || exit 0

mkdir -p "$TXT_DIR" "$WAV_DIR"
TS="$(date +%Y%m%d-%H%M%S)"

# TXT 보관 (provider와 무관하게 항상 남긴다)
printf '%s\n' "$SUMMARY" > "$TXT_DIR/summary-$TS.txt"
ls -1t "$TXT_DIR"/summary-*.txt 2>/dev/null | tail -n +$((MAX_FILES + 1)) | xargs -I {} rm -f {}

# --- provider 선택 ---
# tts-provider.txt 값이 gemini-api/elevenlabs-api면 같은 폴더의 provider 스크립트를 호출한다.
# 파일이 없거나 값이 인식되지 않거나 provider가 실패하면 내장 say 경로로 진행한다.
# WAV 보관·정리는 provider 스크립트가 스스로 담당한다.
PROVIDER=""
[ -s "$PROVIDER_FILE" ] && PROVIDER="$(tr -d '[:space:]' < "$PROVIDER_FILE" | tr '[:upper:]' '[:lower:]')"
PROVIDER_SCRIPT=""
case "$PROVIDER" in
  gemini-api)     PROVIDER_SCRIPT="$SCRIPT_DIR/play-tts-gemini-api.sh" ;;
  elevenlabs-api) PROVIDER_SCRIPT="$SCRIPT_DIR/play-tts-elevenlabs-api.sh" ;;
esac
if [ -n "$PROVIDER_SCRIPT" ] && [ -f "$PROVIDER_SCRIPT" ]; then
  # provider 출력은 로그로 보낸다(훅 stdout을 깨끗하게 유지, JSON stdout을 기대하는 CLI 대비).
  mkdir -p "$AGENT_DIR/log"
  if bash "$PROVIDER_SCRIPT" "$SUMMARY" >> "$AGENT_DIR/log/stop-tts.log" 2>&1; then
    exit 0
  fi
  # API provider 실패(키 누락, 네트워크 오류 등) 시 say로 폴백해 요약이 항상 들리게 한다.
fi

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

# WAV 최신 MAX_FILES개만 유지 (TXT는 보관 직후 정리됨)
ls -1t "$WAV_DIR"/tts-*.wav 2>/dev/null | tail -n +$((MAX_FILES + 1)) | xargs -I {} rm -f {}

exit 0
