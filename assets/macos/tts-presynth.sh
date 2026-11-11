#!/usr/bin/env bash
#
# 요약 음성 미리 합성 (macOS). API provider의 합성 시간을 응답 완료 뒤 대기에서 뺀다.
#
# 에이전트는 tts-summary.txt를 먼저 쓰고 본문을 출력한다. 요약 파일이 써지는 순간
# (PostToolUse: Claude Write|Edit, Codex apply_patch, Antigravity write_file|edit_file) 이 스크립트가 백그라운드로 합성을 시작하고, 본문이 출력되는 동안
# 음성을 캐시에 준비한다. Stop 훅(stop-tts.sh --speak)은 --take로 같은 글의 음성을 꺼내 바로 재생한다.
#
# 모드:
#   (인자 없음)  파일 쓰기 직후 훅. 훅 입력에 요약 파일 경로가 있을 때만 작업자를 띄운다.
#   --worker     stdin 텍스트를 provider로 합성(TTS_NO_PLAY=1)해 캐시에 둔다.
#   --take       stdin 텍스트의 캐시 음성 경로를 출력한다. 합성 중이면 끝날 때까지 기다린다.
#                캐시가 없거나 작업자가 죽었으면 아무것도 출력하지 않는다(호출측이 평소대로 합성).
#
# 캐시 키는 provider·음성·언어·배율·텍스트의 해시다. 설정이나 요약이 바뀌면 키가 달라져
# 옛 음성은 쓰이지 않고 30분 뒤 정리된다. say provider는 로컬 합성이라 대상이 아니다.
# 이식 방법: AGENT_DIR_NAME 기본값만 대상 에이전트 폴더명으로 바꾼다.
#
set +e

AGENT_DIR_NAME="${AGENT_DIR_NAME:-.codex}"   # <-- 이식 시 기본값 변경

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
[ "$AGENT_DIR_NAME" != ".claude" ] || AGENT_DIR="${CLAUDE_CONFIG_DIR:-$AGENT_DIR}"
SUMMARY_FILE="$AGENT_DIR/tts-summary.txt"
CACHE_DIR="$AGENT_DIR/TTS-Summary/presynth"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TAKE_TIMEOUT="${TTS_PRESYNTH_TIMEOUT:-20}"   # 합성 중인 음성을 기다리는 최대 초
START_GRACE=5                                 # 작업자가 시작 표시를 남기기까지 기다리는 초

# 훅 모드는 요약 파일과 무관한 편집을 설정 로드 전에 거른다(모든 Write/Edit마다 불리므로).
# stdin은 먼저 끝까지 읽어 CLI 쪽 쓰기가 막히지 않게 한다.
if [ -z "${1:-}" ]; then
  # Antigravity 훅은 stdout에 JSON을 기대한다. 어느 경로로 끝나든 {}를 낸다.
  [ "$AGENT_DIR_NAME" = ".gemini" ] && trap 'printf "{}\n"' EXIT
  HOOK_INPUT="$(cat 2>/dev/null)"
  case "$HOOK_INPUT" in *tts-summary.txt*) ;; *) exit 0 ;; esac
fi

. "$SCRIPT_DIR/tts-config.sh"
tts_config_load "$AGENT_DIR"

PROVIDER="$(tts_provider)"
case "$PROVIDER" in
  gemini-api)     PROVIDER_SCRIPT="$SCRIPT_DIR/play-tts-gemini-api.sh";     VOICE="$TTS_VOICE_GEMINI" ;;
  elevenlabs-api) PROVIDER_SCRIPT="$SCRIPT_DIR/play-tts-elevenlabs-api.sh"; VOICE="$TTS_VOICE_ELEVENLABS" ;;
  azure-api)      PROVIDER_SCRIPT="$SCRIPT_DIR/play-tts-azure-api.sh";      VOICE="$TTS_VOICE_AZURE" ;;
  *)              exit 0 ;;
esac

# Codex Stop은 요약을 Python read_text로 읽어 CRLF가 LF로 바뀌므로 키에서 CR을 뺀다.
cache_key() {
  { printf '%s\n%s\n%s\n%s\n' "$PROVIDER" "$VOICE" "$TTS_LANGUAGE_CODE" "$(tts_tempo)"; printf '%s' "$1"; } \
    | tr -d '\r' | shasum -a 256 | cut -c1-32
}

# 캐시 음성이 있으면 경로를 출력하고 0을 돌려준다.
print_cached() {
  local f
  for f in "$CACHE_DIR/$1".wav "$CACHE_DIR/$1".mp3; do
    [ -s "$f" ] && { printf '%s' "$f"; return 0; }
  done
  return 1
}

case "${1:-}" in
  --worker)
    TEXT="$(cat)"
    KEY="$(cache_key "$TEXT")"
    PENDING="$CACHE_DIR/$KEY.pending"
    printf '%s' "$$" > "$PENDING"
    OUT="$(TTS_NO_PLAY=1 bash "$PROVIDER_SCRIPT" "$TEXT" 2>> "$AGENT_DIR/log/stop-tts.log")"
    AUDIO="$(printf '%s\n' "$OUT" | sed -n 's/^\[OK\] Saved to: //p' | tail -n 1)"
    if [ -n "$AUDIO" ] && [ -s "$AUDIO" ]; then
      EXT="${AUDIO##*.}"
      mv "$AUDIO" "$CACHE_DIR/$KEY.part.$EXT" && mv "$CACHE_DIR/$KEY.part.$EXT" "$CACHE_DIR/$KEY.$EXT"
    else
      printf 'TTS 미리 합성 실패: %s\n' "$PROVIDER" >> "$AGENT_DIR/log/stop-tts.log"
    fi
    rm -f "$PENDING"
    exit 0
    ;;
  --take)
    TEXT="$(cat)"
    KEY="$(cache_key "$TEXT")"
    PENDING="$CACHE_DIR/$KEY.pending"
    START="$(date +%s)"
    # 계속 기다릴 이유가 있으면 0. 작업자는 음성을 옮긴 뒤 pending을 지우므로, 이 판정 도중에
    # pending이 사라질 수 있다. 그래서 그만 기다릴 때는 언제나 캐시를 한 번 더 본다.
    still_running() {
      [ -f "$PENDING" ] || return 1
      [ $(( $(date +%s) - START )) -lt "$TAKE_TIMEOUT" ] || return 1
      local pid
      pid="$(cat "$PENDING" 2>/dev/null)"
      [ -f "$PENDING" ] || return 1
      if [ -z "$pid" ] || [ "$pid" = "0" ]; then
        [ $(( $(date +%s) - $(stat -f %m "$PENDING" 2>/dev/null || echo 0) )) -lt "$START_GRACE" ]
      else
        kill -0 "$pid" 2>/dev/null
      fi
    }
    while :; do
      print_cached "$KEY" && exit 0
      still_running || { print_cached "$KEY"; exit 0; }
      sleep 0.05
    done
    ;;
esac

# --- PostToolUse 훅 ---
tts_session_muted && exit 0
tts_enabled || exit 0
[ -f "$PROVIDER_SCRIPT" ] || exit 0
# 도구 입력에서 경로를 뽑지 않고, 훅 입력에 이 에이전트의 요약 파일 경로가 들어 있는지만 본다.
# Claude는 tool_input.file_path, Codex는 apply_patch 본문("*** Add File: <절대경로>"),
# Antigravity는 toolCall.args.Path에 경로가 담긴다. 이렇게 형태가 달라도
# 형태가 달라도 같은 판정으로 걸린다. 다른 에이전트의 요약 파일은 폴더 이름이 달라 걸리지 않는다.
case "$HOOK_INPUT" in
  *"$(basename "$AGENT_DIR")/tts-summary.txt"*) ;;
  *) exit 0 ;;
esac

# stop-tts.sh와 같은 방식(명령 치환)으로 읽어야 끝 줄바꿈 처리가 같아 키가 일치한다.
TEXT="$(cat "$SUMMARY_FILE" 2>/dev/null)"
[ -n "${TEXT//[[:space:]]/}" ] || exit 0
# 다른 파일의 내용에 요약 경로 글자가 들어 있어도 걸리므로, 방금 쓴 요약 파일일 때만 합성한다
# (Stop까지 못 간 턴이 남긴 옛 요약을 합성하지 않는다).
[ $(( $(date +%s) - $(stat -f %m "$SUMMARY_FILE" 2>/dev/null || echo 0) )) -le 60 ] || exit 0
# Codex Stop은 CRLF를 LF로 바꿔 넘긴다. 합성하는 글도 같게 맞춘다(키는 cache_key가 CR을 뺀다).
TEXT="${TEXT//$'\r'/}"

mkdir -p "$CACHE_DIR" "$AGENT_DIR/log"
find "$CACHE_DIR" -type f -mmin +30 -delete 2>/dev/null
KEY="$(cache_key "$TEXT")"
ls "$CACHE_DIR/$KEY".* >/dev/null 2>&1 && exit 0
printf '0' > "$CACHE_DIR/$KEY.pending"

# 훅 자손 정리와 무관하게 끝까지 돌도록 일회성 launchd 작업으로 띄운다(stop-tts.sh와 같은 경로).
if [ -n "${TTS_PRESYNTH_INLINE:-}" ]; then
  printf '%s' "$TEXT" | bash "$0" --worker
else
  printf '%s' "$TEXT" | python3 "$SCRIPT_DIR/tts_playback.py" run --launchd \
    --agent-dir "$AGENT_DIR" -- /bin/bash "$0" --worker >> "$AGENT_DIR/log/stop-tts.log" 2>&1 \
    || rm -f "$CACHE_DIR/$KEY.pending"
fi
exit 0
