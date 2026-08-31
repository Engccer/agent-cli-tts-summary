#
# TTS 설정 파일(<에이전트 홈>/TTS-Summary/tts-config.txt) 파서.
# stop-tts.sh, tts-config-context.sh, play-tts-*.sh가 함께 source 한다.
#
# 이 설정 파일이 유일한 정본이다. 예전에 쓰던 개별 파일(tts-provider.txt,
# tts-voice-say.txt, tts-rate-wpm.txt, tts-voice-*.txt, tts-language-code.txt,
# tts-tempo.txt)은 폐지했다.
#
# 사용법:
#   . "$(dirname "$0")/tts-config.sh"
#   tts_config_load "$AGENT_DIR"
#   tts_enabled || exit 0
#

tts_config_load() {
  TTS_ENABLED="on"
  TTS_SPEED="5"
  TTS_VERBOSITY="2"
  TTS_PROVIDER=""
  TTS_VOICE_SAY=""
  TTS_VOICE_GEMINI=""
  TTS_VOICE_ELEVENLABS=""
  TTS_LANGUAGE_CODE="ko-KR"

  TTS_CONFIG_FILE="$1/TTS-Summary/tts-config.txt"
  [ -f "$TTS_CONFIG_FILE" ] || return 0

  local line key value first=1
  while IFS= read -r line || [ -n "$line" ]; do
    # CRLF로 저장된 파일과 UTF-8 BOM을 모두 견딘다.
    line="${line%$'\r'}"
    if [ "$first" = "1" ]; then
      line="${line#$'\xef\xbb\xbf'}"
      first=0
    fi
    case "$line" in
      ''|'#'*) continue ;;
      *=*) ;;
      *) continue ;;
    esac
    key="$(printf '%s' "${line%%=*}" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
    value="$(printf '%s' "${line#*=}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    case "$key" in
      enabled)          TTS_ENABLED="$value" ;;
      speed)            TTS_SPEED="$value" ;;
      verbosity)        TTS_VERBOSITY="$value" ;;
      provider)         TTS_PROVIDER="$value" ;;
      voice_say)        TTS_VOICE_SAY="$value" ;;
      voice_gemini)     TTS_VOICE_GEMINI="$value" ;;
      voice_elevenlabs) TTS_VOICE_ELEVENLABS="$value" ;;
      language_code)    TTS_LANGUAGE_CODE="$value" ;;
    esac
  done < "$TTS_CONFIG_FILE"
}

# 켜져 있으면 0, 꺼져 있으면 1.
tts_enabled() {
  case "$(printf '%s' "$TTS_ENABLED" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')" in
    off|0|false|no) return 1 ;;
    *) return 0 ;;
  esac
}

# provider 값 정규화. 인식되지 않으면 내장 say로 떨어뜨린다.
tts_provider() {
  case "$(printf '%s' "$TTS_PROVIDER" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')" in
    gemini-api)     printf 'gemini-api' ;;
    elevenlabs-api) printf 'elevenlabs-api' ;;
    *)              printf 'say' ;;
  esac
}

# 속도 1~10을 재생 배율 0.5~2.0으로 바꾼다(Windows판과 같은 곡선).
# speed 5가 1.0, 10이 2.0, 1이 0.6.
tts_tempo() {
  awk -v s="$TTS_SPEED" 'BEGIN {
    if (s + 0 == 0 && s != "0") { printf "1.00"; exit }
    if (s < 1) s = 1
    if (s > 10) s = 10
    r = 2 * s - 10
    if (r >= 0) t = 1.0 + r * 0.1; else t = 1.0 + r * 0.05
    if (t < 0.5) t = 0.5
    if (t > 2.0) t = 2.0
    printf "%.2f", t
  }'
}

# say -r 에 넘길 분당 단어 수. 배율 1.0이 200wpm.
tts_rate_wpm() {
  awk -v t="$(tts_tempo)" 'BEGIN { printf "%d", 200 * t + 0.5 }'
}
