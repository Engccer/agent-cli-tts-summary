#
# TTS 설정 파일(<에이전트 홈>/TTS-Summary/tts-config.txt) 파서.
# stop-tts.sh, tts-config-context.sh, play-tts-*.sh, ask-question-tts.sh, tts-config-set.sh가 함께 source 한다.
# 이 설정 파일이 유일한 정본이며 음성·속도를 담는 별도 파일은 없다.
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
  TTS_INTERIM="on"
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
      interim)          TTS_INTERIM="$value" ;;
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

# 응답 완료 전 발화(질문 선택지 안내, 중간 phase 보고)를 할지. 켜져 있으면 0.
# enabled가 꺼져 있으면 이 값과 무관하게 아무것도 읽지 않는다.
tts_interim_enabled() {
  case "$(printf '%s' "$TTS_INTERIM" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')" in
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

# 속도 1~10을 재생 배율 0.5~4.0으로 바꾼다.
# 고정점은 speed 5 = 배율 1.0 = say 200wpm(보통 속도).
#   1~5 구간: 선형(1이 0.6). 느린 쪽은 이미 촘촘하다.
#   5~10 구간: 2.5단계마다 두 배가 되는 기하 곡선(10이 4.0 = say 800wpm).
# 기하로 잡는 이유: 체감 속도는 비율이라 200->400과 400->800이 같은 크기의 한 걸음이다.
# 선형으로 늘리면 위로 갈수록 한 칸의 체감 차이가 줄어 8/9/10이 뭉친다.
# 상한 4.0의 근거: macOS `say`는 800wpm에서 포화한다(그 위로 올려도 길이가 같다).
tts_tempo() {
  awk -v s="$TTS_SPEED" 'BEGIN {
    if (s + 0 == 0 && s != "0") { printf "1.00"; exit }
    if (s < 1) s = 1
    if (s > 10) s = 10
    if (s >= 5) t = exp(((s - 5) / 2.5) * log(2))
    else t = 1.0 + (s - 5) * 0.1
    if (t < 0.5) t = 0.5
    if (t > 4.0) t = 4.0
    printf "%.2f", t
  }'
}

# say -r 에 넘길 분당 단어 수. 배율 1.0이 200wpm.
tts_rate_wpm() {
  awk -v t="$(tts_tempo)" 'BEGIN { printf "%d", 200 * t + 0.5 }'
}

# ffmpeg -filter:a 에 넘길 atempo 필터. 2.0을 넘는 배율은 체인으로 나눈다
# (예: 4.0 -> "atempo=2.0,atempo=2.0000"). 배율이 1.0이면 호출측이 건너뛴다.
#
# 최신 ffmpeg는 나누지 않아도 된다: 8.1의 atempo는 0.5~100을 받고 atempo=4.0이 단독으로
# 동작한다(`ffmpeg -h filter=atempo`). 그런데 옛 빌드는 상한이 2.0이라
# 거부하고, 그때 이 루프는 "속도 설정이 조용히 무시된 원본 속도"로 재생된다(gemini는 원본
# WAV 유지, elevenlabs는 MP3 유지). 스크린 리더 사용자에게 속도는 장식이 아니므로
# ffmpeg 버전을 가리지 않게 체인으로 둔다.
tts_atempo_filter() {
  awk -v t="$(tts_tempo)" 'BEGIN {
    while (t > 2.0000001) { out = out "atempo=2.0,"; t /= 2.0 }
    printf "%satempo=%.4f", out, t
  }'
}
