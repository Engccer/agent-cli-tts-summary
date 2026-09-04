#!/usr/bin/env bash
#
# 직전 요약 음성 파일을 한 번 더 재생한다(macOS). 슬래시 명령(/tts-replay)이 이 스크립트를 부른다.
# 새로 합성하지 않고 TTS-Summary/wav에 보관된 가장 최근 파일을 그대로 튼다(API provider여도 비용 없음).
# 설정의 enabled가 off여도 재생한다. 사용자가 직접 요청한 재생이기 때문이다.
#
# 이 턴의 요약 재생 억제: 재생 뒤에도 이 턴은 Stop hook을 지나므로, 그대로 두면 모델이 쓴
# "다시 재생했습니다" 요약이 새로 합성·재생되어 재생 중인 음성 위에 겹치고, 보관함의 "직전" 자리를
# 그 한 줄이 차지해 다음 /tts-replay가 엉뚱한 파일을 튼다. 그래서 tts-summary.txt를 공백만 담아
# 미리 써 둔다. Stop hook은 공백뿐인 요약 파일을 "이 턴은 재생 없음"으로 보고 보관 없이 조용히
# 지운다. 슬래시 명령 스킬은 모델에게 이 턴에 요약을 쓰지 말라고 지시한다.
# 세션 음소거(TTS_SUMMARY=off) 세션에서는 요약 파일에 손대지 않는다(남아 있는 파일은 다른 세션 것).
#
# 재생은 nohup으로 분리해 슬래시 명령의 `!` 줄이 곧바로 돌아오게 한다(2분 제한 회피).
# 검증: TTS_REPLAY_DRYRUN=1이면 재생하지 않고 file=<경로>를 출력한다.
#
# 이식 방법: AGENT_DIR_NAME 기본값을 대상 에이전트 폴더명으로 바꾼다(.claude / .codex / .gemini).
#
set +e

AGENT_DIR_NAME="${AGENT_DIR_NAME:-.claude}"   # <-- 이식 시 기본값만 변경

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WAV_DIR="$AGENT_DIR/TTS-Summary/wav"
SUMMARY_FILE="$AGENT_DIR/tts-summary.txt"

. "$SCRIPT_DIR/tts-config.sh"
tts_config_load "$AGENT_DIR"

# provider에 따라 wav/aiff(say, gemini) 또는 mp3(elevenlabs, ffmpeg 없을 때)가 남는다. afplay는 셋 다 튼다.
LATEST="$(ls -1t "$WAV_DIR"/tts-*.wav "$WAV_DIR"/tts-*.aiff "$WAV_DIR"/tts-*.mp3 2>/dev/null | head -n 1)"
if [ -z "$LATEST" ]; then
  echo "다시 재생할 요약 음성이 없습니다."
  exit 0
fi

# 파일명 tts-YYYYMMDD-HHMMSS.* 에서 생성 시각을 읽는다.
NAME="$(basename "$LATEST")"
STAMP="${NAME#tts-}"
WHEN=""
case "$STAMP" in
  [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]*)
    WHEN="${STAMP:0:4}-${STAMP:4:2}-${STAMP:6:2} ${STAMP:9:2}:${STAMP:11:2}:${STAMP:13:2}" ;;
esac

if ! tts_session_muted; then
  printf '\n' > "$SUMMARY_FILE"
fi

if [ "${TTS_REPLAY_DRYRUN:-0}" = "1" ]; then
  printf 'file=%s\n' "$LATEST"
else
  nohup /usr/bin/afplay "$LATEST" >/dev/null 2>&1 &
fi

if [ -n "$WHEN" ]; then
  printf '직전 요약 음성(%s)을 다시 재생합니다.\n' "$WHEN"
else
  printf '직전 요약 음성을 다시 재생합니다.\n'
fi
exit 0
