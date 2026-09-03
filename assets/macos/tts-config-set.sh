#!/usr/bin/env bash
#
# TTS 설정 파일(<에이전트 홈>/TTS-Summary/tts-config.txt)을 터미널에서 바꾸는 설정기(macOS).
# 슬래시 명령(/tts)이 이 스크립트를 부른다. 훅이 매 턴 설정 파일을 새로 읽으므로
# 여기서 바꾼 값은 같은 턴의 재생부터 바로 적용되고 세션 재시작이 필요 없다.
#
# 사용법:
#   tts-config-set.sh                 현재 설정 표시
#   tts-config-set.sh on | off        음성 요약 켬/끔
#   tts-config-set.sh speed <1~10>    말하기 속도(소수점 허용)
#   tts-config-set.sh verbosity <1~3> 요약 상세 정도
#   tts-config-set.sh interim on | off 질문 선택지 안내·중간 phase 보고 여부
#
# 주석과 나머지 줄은 그대로 두고 해당 "키=값" 줄만 바꾼다. 키가 없으면 끝에 덧붙인다.
# 첫 줄의 UTF-8 BOM은 벗겨 저장하고(파서는 있든 없든 읽는다), CRLF 줄은 CRLF로 유지한다.
# 슬래시 명령은 인자 전체를 따옴표로 감싼 한 문자열로 넘기므로 아래에서 공백 기준으로 다시 나눈다.
#
# 이식 방법: AGENT_DIR_NAME 기본값을 대상 에이전트 폴더명으로 바꾼다(.claude / .codex / .gemini).
# 테스트나 임시 점검에서는 같은 이름의 환경 변수로 덮어쓸 수 있다.
#
set -e

AGENT_DIR_NAME="${AGENT_DIR_NAME:-.claude}"   # <-- 이식 시 기본값만 변경

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$AGENT_DIR/TTS-Summary/tts-config.txt"

. "$SCRIPT_DIR/tts-config.sh"

# 인자를 공백 기준으로 다시 나눈다(글로브 확장 없이). "speed 8" 한 덩어리로 와도 두 인자가 된다.
set -f; set -- $*; set +f

usage() {
  cat <<'EOF'
사용법: tts [on|off] | tts speed <1~10> | tts verbosity <1~3> | tts interim <on|off>
인자 없이 실행하면 현재 설정을 보여준다.
EOF
}

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

# 설정 파일의 "키=값" 줄 하나를 바꾼다. 주석·빈 줄·다른 키는 그대로 둔다.
set_key() {
  local key="$1" value="$2" tmp
  [ -f "$CONFIG_FILE" ] || fail "설정 파일이 없습니다: $CONFIG_FILE"
  tmp="$(mktemp "$CONFIG_FILE.XXXXXX")"
  # macOS 기본 awk는 정규식의 \x 이스케이프를 모르므로 BOM은 awk에 넘기기 전에 bash에서 벗긴다.
  if [ "$(head -c 3 "$CONFIG_FILE")" = $'\xef\xbb\xbf' ]; then
    tail -c +4 "$CONFIG_FILE"
  else
    cat "$CONFIG_FILE"
  fi | awk -v key="$key" -v value="$value" '
    BEGIN { done = 0 }
    {
      line = $0
      cr = ""
      if (sub(/\r$/, "", line)) cr = "\r"
      if (line ~ /^[[:space:]]*#/ || line !~ /=/) { print; next }
      split(line, kv, "=")
      k = kv[1]
      gsub(/[[:space:]]/, "", k)
      if (tolower(k) == key) {
        if (!done) { print key "=" value cr; done = 1 }
        next
      }
      print
    }
    END { if (!done) print key "=" value }
  ' > "$tmp"
  mv "$tmp" "$CONFIG_FILE"
}

show() {
  tts_config_load "$AGENT_DIR"
  local state interim
  if tts_enabled; then state="켬"; else state="끔"; fi
  if tts_interim_enabled; then interim="켬"; else interim="끔"; fi
  printf 'TTS 음성 요약 %s, 속도 %s(%swpm), 상세 %s단계, 선택지·중간 보고 %s, 프로바이더 %s' \
    "$state" "$TTS_SPEED" "$(tts_rate_wpm)" "$TTS_VERBOSITY" "$interim" "$(tts_provider)"
  case "$(tts_provider)" in
    say)            [ -n "$TTS_VOICE_SAY" ] && printf ', 음성 %s' "$TTS_VOICE_SAY" ;;
    gemini-api)     [ -n "$TTS_VOICE_GEMINI" ] && printf ', 음성 %s' "$TTS_VOICE_GEMINI" ;;
    elevenlabs-api) [ -n "$TTS_VOICE_ELEVENLABS" ] && printf ', 음성 %s' "$TTS_VOICE_ELEVENLABS" ;;
  esac
  printf '\n'
}

case "${1:-}" in
  '')
    show
    ;;
  on|off)
    [ $# -eq 1 ] || fail "$(usage)"
    set_key enabled "$1"
    show
    ;;
  speed)
    [ $# -eq 2 ] || fail "$(usage)"
    case "$2" in
      *[!0-9.]*|''|.|*.*.*) fail "속도는 1~10 사이 숫자여야 합니다(소수점 허용): $2" ;;
    esac
    awk -v v="$2" 'BEGIN { exit !(v >= 1 && v <= 10) }' || fail "속도는 1~10 사이여야 합니다: $2"
    set_key speed "$2"
    show
    ;;
  verbosity)
    [ $# -eq 2 ] || fail "$(usage)"
    case "$2" in
      1|2|3) ;;
      *) fail "상세 정도는 1, 2, 3 중 하나여야 합니다: $2" ;;
    esac
    set_key verbosity "$2"
    show
    ;;
  interim)
    [ $# -eq 2 ] || fail "$(usage)"
    case "$2" in
      on|off) ;;
      *) fail "interim 값은 on 또는 off여야 합니다: $2" ;;
    esac
    set_key interim "$2"
    show
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    fail "$(usage)"
    ;;
esac
