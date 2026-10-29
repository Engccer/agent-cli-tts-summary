#!/usr/bin/env bash
#
# Azure AI Speech TTS provider (macOS) - 내장 say 대신 Azure 한국어 neural 음색을 쓸 때 사용한다.
# 설정 파일의 provider에 "azure-api"를 적으면 stop-tts.sh가 호출한다.
# 이 스킬에 동봉된 assets/tts/azure_tts.py로 WAV를 직접 받아 보관 폴더에 옮기고 afplay로 재생한다.
#
# 전제: 환경 변수 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION, python3(표준 라이브러리만), CONVERTER_SCRIPT 경로 존재.
# 키는 ~/.zshenv에 export로 둔다. 키를 저장하기 전에 띄운 CLI 세션은 프로세스 환경에 값이 없으므로
# 그때는 zsh가 ~/.zshenv를 읽은 값을 가져온다(Windows 판이 사용자 환경 변수에서 읽는 것과 같은 역할).
# 속도는 2배까지 SSML <prosody rate>로 합성 단계에서 넣고, 2배를 넘는 부분(speed 7.5 초과)만 ffmpeg atempo로 보탠다.
# ffmpeg가 없으면 2배로 재생한다.
# 이식 방법: AGENT_DIR_NAME, CONVERTER_SCRIPT 두 곳을 환경에 맞게 바꾼다.
# 음성·언어는 TTS-Summary/tts-config.txt의 voice_azure, language_code로 제어한다.
# 성공 시 exit 0, 실패 시 exit 1 (stop-tts.sh가 실패를 감지해 say로 폴백한다).
#
set +e

AGENT_DIR_NAME=".codex"   # <-- 이식 시 변경 (.claude/.codex/.gemini)
CONVERTER_SCRIPT="<SKILL_DIR>/assets/tts/azure_tts.py"  # <-- 이 스킬 설치 폴더에 동봉된 azure_tts.py의 절대 경로로 바꾼다(예: ~/.claude/skills/agent-cli-tts-summary/assets/tts/azure_tts.py)

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
WAV_DIR="$AGENT_DIR/TTS-Summary/wav"
TEMP_DIR="$AGENT_DIR/TTS-Summary/tmp"
LOG_DIR="$AGENT_DIR/log"
LOG_FILE="$LOG_DIR/azure-api-tts.log"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/tts-config.sh"
tts_config_load "$AGENT_DIR"
MAX_FILES=10

TEXT="$1"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG_FILE"; }

mkdir -p "$WAV_DIR" "$TEMP_DIR" "$LOG_DIR"

VOICE="${TTS_VOICE_AZURE:-ko-KR-SunHiNeural}"
LANGUAGE="${TTS_LANGUAGE_CODE:-ko-KR}"

if [ -z "$AZURE_SPEECH_KEY" ] || [ -z "$AZURE_SPEECH_REGION" ]; then
  if command -v zsh >/dev/null 2>&1; then
    [ -n "$AZURE_SPEECH_KEY" ] || AZURE_SPEECH_KEY="$(zsh -c 'printf %s "$AZURE_SPEECH_KEY"' 2>/dev/null)"
    [ -n "$AZURE_SPEECH_REGION" ] || AZURE_SPEECH_REGION="$(zsh -c 'printf %s "$AZURE_SPEECH_REGION"' 2>/dev/null)"
    export AZURE_SPEECH_KEY AZURE_SPEECH_REGION
  fi
fi

if [ -z "${TEXT//[[:space:]]/}" ]; then log "ERROR: empty text"; exit 1; fi
if [ -z "$AZURE_SPEECH_KEY" ]; then log "ERROR: AZURE_SPEECH_KEY is not set"; exit 1; fi
if [ -z "$AZURE_SPEECH_REGION" ]; then log "ERROR: AZURE_SPEECH_REGION is not set"; exit 1; fi
if [ ! -f "$CONVERTER_SCRIPT" ]; then log "ERROR: converter script not found: $CONVERTER_SCRIPT"; exit 1; fi
command -v python3 >/dev/null 2>&1 || { log "ERROR: python3 not found"; exit 1; }

TS="$(date +%Y%m%d-%H%M%S)-$$"
INPUT_FILE="$TEMP_DIR/az-$TS.txt"
AUDIO_FILE="$WAV_DIR/tts-$TS.wav"

# 배율을 합성분(최대 2.0)과 후처리분으로 나눈다.
TEMPO="$(tts_tempo)"
SYNTH_TEMPO="$(awk -v t="$TEMPO" 'BEGIN { printf "%.4f", (t > 2.0 ? 2.0 : t) }')"
RESIDUAL="$(awk -v t="$TEMPO" 'BEGIN { printf "%.4f", (t > 2.0 ? t / 2.0 : 1.0) }')"

printf '%s' "$TEXT" > "$INPUT_FILE"
log "Starting Azure API TTS voice=$VOICE language=$LANGUAGE tempo=$TEMPO synth=$SYNTH_TEMPO chars=${#TEXT}"
python3 "$CONVERTER_SCRIPT" "$INPUT_FILE" --voice "$VOICE" --language-code "$LANGUAGE" \
  --tempo "$SYNTH_TEMPO" --output "$AUDIO_FILE" < /dev/null >> "$LOG_FILE" 2>&1
rm -f "$INPUT_FILE"

if [ ! -s "$AUDIO_FILE" ]; then
  rm -f "$AUDIO_FILE"
  log "ERROR: expected WAV output was not created"
  exit 1
fi

if [ "$RESIDUAL" != "1.0000" ]; then
  if command -v ffmpeg >/dev/null 2>&1; then
    ADJUSTED="$WAV_DIR/tts-$TS.tempo.wav"
    if ffmpeg -y -i "$AUDIO_FILE" -filter:a "atempo=$RESIDUAL" "$ADJUSTED" >> "$LOG_FILE" 2>&1 && [ -s "$ADJUSTED" ]; then
      mv "$ADJUSTED" "$AUDIO_FILE"
    else
      rm -f "$ADJUSTED"
      log "Residual tempo failed; keeping 2.0x WAV"
    fi
  else
    log "ffmpeg not found; skipping residual tempo=$RESIDUAL (playing at Azure max 2.0x)"
  fi
fi

echo "[OK] Saved to: $AUDIO_FILE"
echo "[VOICE] Voice used: $VOICE (Azure API TTS)"
log "Saved to: $AUDIO_FILE"

# 오디오만 생성하고 재생은 생략하려면 환경 변수 TTS_NO_PLAY=1 (Windows provider와 동일 규약).
# 합성은 성공했으므로 재생 실패는 provider 실패로 치지 않는다(폴백 재합성 방지).
if [ -z "$TTS_NO_PLAY" ]; then
  afplay "$AUDIO_FILE" 2>/dev/null || log "Playback failed (audio archived)"
fi

ls -1t "$WAV_DIR"/tts-*.wav 2>/dev/null | tail -n +$((MAX_FILES + 1)) | xargs -I {} rm -f {}

exit 0
