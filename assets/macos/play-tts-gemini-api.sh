#!/usr/bin/env bash
#
# Gemini API TTS provider (macOS) - 내장 say 대신 고품질 Gemini 음색을 쓰고 싶을 때 사용한다.
# 설정 파일의 provider에 "gemini-api"를 적으면 stop-tts.sh가 호출한다.
# 이 스킬에 동봉된 assets/tts/gemini_tts.py로 WAV를 만들어 보관 폴더에 옮기고 afplay로 재생한다.
#
# 전제: 환경 변수 GEMINI_API_KEY 설정(유료 API), python3, CONVERTER_SCRIPT 경로 존재,
#       (선택) ffmpeg로 속도 보정.
# 이식 방법: AGENT_DIR_NAME, CONVERTER_SCRIPT 두 곳을 환경에 맞게 바꾼다.
# 음성·언어·속도는 TTS-Summary/tts-config.txt에서 읽는다(voice_gemini, language_code, speed).
# 파싱은 같은 폴더의 tts-config.sh가 담당한다.
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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAX_FILES=10

. "$SCRIPT_DIR/tts-config.sh"
tts_config_load "$AGENT_DIR"

TEXT="$1"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG_FILE"; }

mkdir -p "$WAV_DIR" "$TEMP_DIR" "$LOG_DIR"

VOICE="${TTS_VOICE_GEMINI:-Puck}"
LANGUAGE_CODE="${TTS_LANGUAGE_CODE:-ko-KR}"

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

# 속도 보정: 설정의 speed에서 나온 배율을 ffmpeg atempo로 적용한다. 실패해도 원본 유지.
if command -v ffmpeg >/dev/null 2>&1; then
  TEMPO="$(tts_tempo)"
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
