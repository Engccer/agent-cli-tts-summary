#!/usr/bin/env bash
#
# Gemini API TTS provider (macOS) - 내장 say 대신 고품질 Gemini 음색을 쓰고 싶을 때 사용한다.
# 에이전트 홈의 tts-provider.txt에 "gemini-api"를 적으면 stop-tts.sh가 호출한다.
# 이 스킬에 동봉된 assets/tts/gemini_tts.py로 WAV를 만들어 보관 폴더에 옮기고 afplay로 재생한다.
#
# 전제: 환경 변수 GEMINI_API_KEY 설정(유료 API), python3, CONVERTER_SCRIPT 경로 존재,
#       (선택) ffmpeg + tts-tempo.txt로 속도 보정.
# 이식 방법: AGENT_DIR_NAME, CONVERTER_SCRIPT 두 곳을 환경에 맞게 바꾼다.
# 음성·언어는 에이전트 홈의 텍스트 파일로 제어한다(없으면 아래 기본값 사용):
#   tts-voice-gemini.txt    음성 이름(예: Puck, Kore)
#   tts-language-code.txt   언어 코드(예: ko-KR, en-US). 요약 언어 선택과 짝을 맞춘다.
#   tts-tempo.txt           재생 속도 배율(예: 1.3). say의 tts-rate-wpm.txt와 별개이며 ffmpeg가 필요.
# 성공 시 exit 0, 실패 시 exit 1 (stop-tts.sh가 실패를 감지해 say로 폴백한다).
#
set +e

AGENT_DIR_NAME=".codex"   # <-- 이식 시 변경 (.claude/.codex/.gemini)
CONVERTER_SCRIPT="<SKILL_DIR>/assets/tts/gemini_tts.py"  # <-- 이 스킬 설치 폴더에 동봉된 gemini_tts.py의 절대 경로로 바꾼다(예: ~/.claude/skills/agent-cli-tts-summary/assets/tts/gemini_tts.py)

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
WAV_DIR="$AGENT_DIR/TTS-Summary/wav"
TEMP_DIR="$AGENT_DIR/TTS-Summary/tmp"
LOG_DIR="$AGENT_DIR/log"
LOG_FILE="$LOG_DIR/gemini-api-tts.log"
VOICE_FILE="$AGENT_DIR/tts-voice-gemini.txt"
LANGUAGE_CODE_FILE="$AGENT_DIR/tts-language-code.txt"
TEMPO_FILE="$AGENT_DIR/tts-tempo.txt"
MAX_FILES=10

TEXT="$1"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG_FILE"; }

mkdir -p "$WAV_DIR" "$TEMP_DIR" "$LOG_DIR"

VOICE="Puck"
[ -s "$VOICE_FILE" ] && VOICE="$(tr -d '\n' < "$VOICE_FILE")"
LANGUAGE_CODE="ko-KR"
[ -s "$LANGUAGE_CODE_FILE" ] && LANGUAGE_CODE="$(tr -d '[:space:]' < "$LANGUAGE_CODE_FILE")"

if [ -z "${TEXT//[[:space:]]/}" ]; then log "ERROR: empty text"; exit 1; fi
if [ -z "$GEMINI_API_KEY" ]; then log "ERROR: GEMINI_API_KEY is not set"; exit 1; fi
if [ ! -f "$CONVERTER_SCRIPT" ]; then log "ERROR: converter script not found: $CONVERTER_SCRIPT"; exit 1; fi
command -v python3 >/dev/null 2>&1 || { log "ERROR: python3 not found"; exit 1; }

TS="$(date +%Y%m%d-%H%M%S)-$$"
INPUT_FILE="$TEMP_DIR/tts-$TS.txt"
EXPECTED_WAV="$TEMP_DIR/tts-${TS}_gemini_tts.wav"
AUDIO_FILE="$WAV_DIR/tts-$TS.wav"

printf '%s' "$TEXT" > "$INPUT_FILE"
log "Starting Gemini API TTS voice=$VOICE language=$LANGUAGE_CODE chars=${#TEXT}"
python3 "$CONVERTER_SCRIPT" "$INPUT_FILE" --voice "$VOICE" --language-code "$LANGUAGE_CODE" \
  < /dev/null >> "$LOG_FILE" 2>&1
rm -f "$INPUT_FILE"

if [ ! -f "$EXPECTED_WAV" ]; then
  log "ERROR: expected WAV output was not created"
  exit 1
fi
mv "$EXPECTED_WAV" "$AUDIO_FILE"

# 속도 보정: tts-tempo.txt(배율)가 있고 ffmpeg가 있으면 atempo를 적용한다. 실패해도 원본 유지.
if [ -s "$TEMPO_FILE" ] && command -v ffmpeg >/dev/null 2>&1; then
  TEMPO="$(tr -d '[:space:]' < "$TEMPO_FILE")"
  case "$TEMPO" in
    ''|1|1.0|1.00) : ;;
    *)
      ADJUSTED="$TEMP_DIR/tts-$TS.tempo.wav"
      if ffmpeg -y -i "$AUDIO_FILE" -filter:a "atempo=$TEMPO" "$ADJUSTED" >> "$LOG_FILE" 2>&1; then
        mv "$ADJUSTED" "$AUDIO_FILE"
      else
        rm -f "$ADJUSTED"
        log "Tempo adjustment failed tempo=$TEMPO; keeping original WAV"
      fi
      ;;
  esac
fi

echo "[OK] Saved to: $AUDIO_FILE"
echo "[VOICE] Voice used: $VOICE (Gemini API TTS)"
log "Saved to: $AUDIO_FILE"

# WAV만 생성하고 재생은 생략하려면 환경 변수 TTS_NO_PLAY=1 (Windows provider와 동일 규약).
# 합성은 성공했으므로 재생 실패는 provider 실패로 치지 않는다(폴백 재합성 방지).
if [ -z "$TTS_NO_PLAY" ]; then
  afplay "$AUDIO_FILE" 2>/dev/null || log "Playback failed (WAV archived)"
fi

# 최신 MAX_FILES개만 유지
ls -1t "$WAV_DIR"/tts-*.wav 2>/dev/null | tail -n +$((MAX_FILES + 1)) | xargs -I {} rm -f {}

exit 0
