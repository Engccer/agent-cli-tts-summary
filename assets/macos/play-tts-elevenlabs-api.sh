#!/usr/bin/env bash
#
# ElevenLabs API TTS provider (macOS) - 내장 say 대신 고품질 ElevenLabs 음색을 쓰고 싶을 때 사용한다.
# 에이전트 홈의 tts-provider.txt에 "elevenlabs-api"를 적으면 stop-tts.sh가 호출한다.
# 이 스킬에 동봉된 assets/tts/elevenlabs_tts.py로 MP3를 만들어 보관 폴더에 옮기고 afplay로 재생한다.
# ffmpeg가 있으면 WAV로 변환(+속도 보정)해 보관을 통일하고, 없으면 MP3 그대로 재생·보관한다
# (afplay는 MP3도 재생 가능하므로 ffmpeg는 필수가 아니다. Windows 판과 다른 점).
#
# 전제: 환경 변수 ELEVENLABS_API_KEY 설정(유료 API), python3, CONVERTER_SCRIPT 경로 존재,
#       (선택) ffmpeg + tts-tempo.txt로 WAV 변환·속도 보정.
# 이식 방법: AGENT_DIR_NAME, CONVERTER_SCRIPT 두 곳을 환경에 맞게 바꾼다.
# 음성은 에이전트 홈의 tts-voice-elevenlabs.txt로 제어한다(없으면 아래 기본값 사용).
# 검증된 구성: 모델 eleven_turbo_v2_5(짧은 요약 기준 v3보다 합성 지연이 짧음), 음성 Yuna(한국어).
# 요약 언어를 바꿨다면 그 언어에 맞는 음성 이름으로 바꾼다(모델은 다국어 지원).
# 성공 시 exit 0, 실패 시 exit 1 (stop-tts.sh가 실패를 감지해 say로 폴백한다).
#
set +e

AGENT_DIR_NAME=".codex"   # <-- 이식 시 변경 (.claude/.codex/.gemini)
CONVERTER_SCRIPT="<SKILL_DIR>/assets/tts/elevenlabs_tts.py"  # <-- 이 스킬 설치 폴더에 동봉된 elevenlabs_tts.py의 절대 경로로 바꾼다(예: ~/.claude/skills/agent-cli-tts-summary/assets/tts/elevenlabs_tts.py)
MODEL="eleven_turbo_v2_5"   # 빈 문자열이면 elevenlabs_tts.py 기본값(eleven_v3)

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
WAV_DIR="$AGENT_DIR/TTS-Summary/wav"
TEMP_DIR="$AGENT_DIR/TTS-Summary/tmp"
LOG_DIR="$AGENT_DIR/log"
LOG_FILE="$LOG_DIR/elevenlabs-api-tts.log"
VOICE_FILE="$AGENT_DIR/tts-voice-elevenlabs.txt"
TEMPO_FILE="$AGENT_DIR/tts-tempo.txt"
MAX_FILES=10

TEXT="$1"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG_FILE"; }

mkdir -p "$WAV_DIR" "$TEMP_DIR" "$LOG_DIR"

VOICE="Yuna"
[ -s "$VOICE_FILE" ] && VOICE="$(tr -d '\n' < "$VOICE_FILE")"

if [ -z "${TEXT//[[:space:]]/}" ]; then log "ERROR: empty text"; exit 1; fi
if [ -z "$ELEVENLABS_API_KEY" ]; then log "ERROR: ELEVENLABS_API_KEY is not set"; exit 1; fi
if [ ! -f "$CONVERTER_SCRIPT" ]; then log "ERROR: converter script not found: $CONVERTER_SCRIPT"; exit 1; fi
command -v python3 >/dev/null 2>&1 || { log "ERROR: python3 not found"; exit 1; }

TS="$(date +%Y%m%d-%H%M%S)-$$"
INPUT_FILE="$TEMP_DIR/el-$TS.txt"
EXPECTED_MP3="$TEMP_DIR/el-${TS}_elevenlabs.mp3"

printf '%s' "$TEXT" > "$INPUT_FILE"
log "Starting ElevenLabs API TTS voice=$VOICE model=$MODEL chars=${#TEXT}"
# --single: 요약은 항상 단일 화자이므로 다중 화자 자동 감지를 끈다.
MODEL_ARGS=()
[ -n "$MODEL" ] && MODEL_ARGS=(--model "$MODEL")
python3 "$CONVERTER_SCRIPT" "$INPUT_FILE" --single --voice "$VOICE" "${MODEL_ARGS[@]}" \
  < /dev/null >> "$LOG_FILE" 2>&1
rm -f "$INPUT_FILE"

if [ ! -f "$EXPECTED_MP3" ]; then
  log "ERROR: expected MP3 output was not created"
  exit 1
fi

TEMPO=""
[ -s "$TEMPO_FILE" ] && TEMPO="$(tr -d '[:space:]' < "$TEMPO_FILE")"
case "$TEMPO" in 1|1.0|1.00) TEMPO="" ;; esac

AUDIO_FILE="$WAV_DIR/tts-$TS.mp3"
if command -v ffmpeg >/dev/null 2>&1; then
  # ffmpeg가 있으면 WAV로 변환하고, 속도 보정도 같은 패스에서 적용한다.
  CANDIDATE="$WAV_DIR/tts-$TS.wav"
  if [ -n "$TEMPO" ]; then
    ffmpeg -y -i "$EXPECTED_MP3" -filter:a "atempo=$TEMPO" -ar 44100 -ac 2 -c:a pcm_s16le "$CANDIDATE" >> "$LOG_FILE" 2>&1
  else
    ffmpeg -y -i "$EXPECTED_MP3" -ar 44100 -ac 2 -c:a pcm_s16le "$CANDIDATE" >> "$LOG_FILE" 2>&1
  fi
  if [ -f "$CANDIDATE" ]; then
    AUDIO_FILE="$CANDIDATE"
    rm -f "$EXPECTED_MP3"
  else
    log "ffmpeg conversion failed; keeping MP3"
    mv "$EXPECTED_MP3" "$AUDIO_FILE"
  fi
else
  [ -n "$TEMPO" ] && log "ffmpeg not found; skipping tempo adjustment tempo=$TEMPO"
  mv "$EXPECTED_MP3" "$AUDIO_FILE"
fi

echo "[OK] Saved to: $AUDIO_FILE"
echo "[VOICE] Voice used: $VOICE (ElevenLabs API TTS / ${MODEL:-eleven_v3})"
log "Saved to: $AUDIO_FILE"

# 오디오만 생성하고 재생은 생략하려면 환경 변수 TTS_NO_PLAY=1 (Windows provider와 동일 규약).
# 합성은 성공했으므로 재생 실패는 provider 실패로 치지 않는다(폴백 재합성 방지).
if [ -z "$TTS_NO_PLAY" ]; then
  afplay "$AUDIO_FILE" 2>/dev/null || log "Playback failed (audio archived)"
fi

# 최신 MAX_FILES개만 유지 (WAV/MP3 각각)
ls -1t "$WAV_DIR"/tts-*.wav 2>/dev/null | tail -n +$((MAX_FILES + 1)) | xargs -I {} rm -f {}
ls -1t "$WAV_DIR"/tts-*.mp3 2>/dev/null | tail -n +$((MAX_FILES + 1)) | xargs -I {} rm -f {}

exit 0
