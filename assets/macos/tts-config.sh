#
# TTS 설정 파일(<에이전트 홈>/TTS-Summary/tts-config.txt) 파서.
# stop-tts.sh, tts-config-context.sh, play-tts-*.sh, ask-question-tts.sh, tts-config-set.sh, tts-replay.sh가 함께 source 한다.
# 이 설정 파일이 유일한 정본이며 음성·속도를 담는 별도 파일은 없다.
#

# 모델이 실행한 제어 명령의 안내 응답을 다음 전문 낭독에서 제외한다.
# 직접 터미널 실행처럼 세션 ID가 없을 때는 기록하지 않는다.
tts_mark_control_turn() {
  local agent session_id
  case "${AGENT_DIR_NAME:-}" in
    .codex) agent=codex; session_id="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-}}" ;;
    .gemini) agent=agy; session_id="${ANTIGRAVITY_CONVERSATION_ID:-}" ;;
    *) return 0 ;;
  esac
  [ -n "$session_id" ] || return 0
  [ -f "$SCRIPT_DIR/tts_transcripts.py" ] || return 0
  python3 "$SCRIPT_DIR/tts_transcripts.py" mark --agent "$agent" \
    --agent-dir "$AGENT_DIR" --session-id "$session_id" || true
}

# 세션 식별자가 계약(영문·숫자·밑줄·하이픈 1~128자)에 맞으면 0. 경로에 그대로 쓰이므로 그 밖의 값은 버린다.
# 로캘에 따라 달라지는 범위식([A-Z]) 대신 허용 문자를 그대로 나열한다.
tts_valid_session_id() {
  case "${1:-}" in
    ''|*[!abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-]*) return 1 ;;
  esac
  [ "${#1}" -le 128 ]
}

# 훅 payload(JSON)에서 이 세션의 식별자를 출력한다. 최상위 session_id(Claude·Codex), 없으면
# conversationId(Antigravity), 그것도 없는 Antigravity는 환경 변수 ANTIGRAVITY_CONVERSATION_ID를 쓴다.
# 계약에 맞지 않거나 알 수 없으면 아무것도 출력하지 않는다.
tts_session_id() {
  local sid
  sid="$(printf '%s' "${1:-}" | python3 -c '
import json, os, re, sys
try:
    data = json.loads(sys.stdin.read())
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}
sid = data.get("session_id") or data.get("conversationId")
if not sid and sys.argv[1] == ".gemini":
    sid = os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
# 명령 치환이 끝 줄바꿈을 떼기 전에 여기서 검사한다.
if isinstance(sid, str) and re.fullmatch("[A-Za-z0-9_-]{1,128}", sid):
    print(sid, end="")
' "${AGENT_DIR_NAME:-}" 2>/dev/null)"
  tts_valid_session_id "$sid" && printf '%s' "$sid"
}

# 슬래시 명령·스킬이 부른 스크립트가 아는 세션 식별자(첫 인자 또는 CLI가 심은 환경 변수)를 출력한다.
tts_cli_session_id() {
  local sid="${1:-}"
  if [ -z "$sid" ]; then
    case "${AGENT_DIR_NAME:-}" in
      .claude) sid="${CLAUDE_SESSION_ID:-}" ;;
      .codex)  sid="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-}}" ;;
      .gemini) sid="${ANTIGRAVITY_CONVERSATION_ID:-}" ;;
    esac
  fi
  tts_valid_session_id "$sid" && printf '%s' "$sid"
}

# 요약 파일 경로. 세션 식별자가 있으면 그 세션 전용 파일(<에이전트 홈>/TTS-Summary/pending/<sid>.txt),
# 없으면 공용 파일(<에이전트 홈>/tts-summary.txt)이다. 인자: 에이전트 홈, 세션 식별자.
tts_summary_file() {
  if tts_valid_session_id "${2:-}"; then
    printf '%s/TTS-Summary/pending/%s.txt' "$1" "$2"
  else
    printf '%s/tts-summary.txt' "$1"
  fi
}

# 글($1)에 <폴더명($2)>/TTS-Summary/pending/<sid>.txt 꼴의 세션 요약 파일 경로가 들어 있으면 0을 돌려주고
# TTS_PENDING_SID에 그 세션 식별자를 담는다.
tts_pending_file_in() {
  [[ "$1" =~ "$2"/TTS-Summary/pending/([A-Za-z0-9_-]+)\.txt ]] || return 1
  tts_valid_session_id "${BASH_REMATCH[1]}" || return 1
  TTS_PENDING_SID="${BASH_REMATCH[1]}"
}

# 이 턴의 요약 재생을 억제하는 공백 요약 파일을 쓴다(/tts-replay, /tts-read, /tts-pause).
# 세션을 알면 그 세션 파일에, 모르면 공용 파일에 쓴다. 인자: 에이전트 홈, 세션 식별자.
tts_suppress_summary() {
  local file
  file="$(tts_summary_file "$1" "${2:-}")"
  mkdir -p "${file%/*}" && printf '\n' > "$file"
}

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
  TTS_VOICE_AZURE=""
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
      voice_azure)      TTS_VOICE_AZURE="$value" ;;
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

# 이 세션에 한해 요약 루프를 끄는 환경 변수. 병렬 세션 런처(parallel-sessions 스킬)가 작업
# 세션을 띄울 때 TTS_SUMMARY=off를 심는다. 설정 파일의 enabled와 달리 그 세션의 프로세스
# 트리에만 걸리므로(훅은 CLI의 자식 프로세스라 상속) 코디네이터·단독 세션은 영향을 받지 않는다.
# 꺼져 있으면 0.
tts_session_muted() {
  case "$(printf '%s' "${TTS_SUMMARY:-}" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')" in
    off|0|false|no) return 0 ;;
    *) return 1 ;;
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
    azure-api)      printf 'azure-api' ;;
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
