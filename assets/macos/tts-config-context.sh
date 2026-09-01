#!/usr/bin/env bash
#
# UserPromptSubmit hook (macOS) - TTS 설정의 사용 여부와 상세 정도를 에이전트에게 알린다.
# 재생은 Stop hook이 담당하고, 이 훅은 "요약을 쓸지, 얼마나 자세히 쓸지"만 전달한다.
# 설정을 바꾸면 다음 턴부터 바로 반영된다.
# Claude에는 일반 텍스트를, Codex에는 hookSpecificOutput.additionalContext JSON을 출력한다.
#
# 이식 방법: AGENT_DIR_NAME 기본값을 대상 에이전트 폴더명으로 바꾼다(.claude / .codex / .gemini).
# 테스트나 임시 점검에서는 같은 이름의 환경 변수로 덮어쓸 수 있다.
#
set +e

AGENT_DIR_NAME="${AGENT_DIR_NAME:-.codex}"   # <-- 이식 시 기본값만 변경

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/tts-config.sh" 2>/dev/null || exit 0
tts_config_load "$AGENT_DIR"

emit_context() {
  local message="$1"
  if [ "$AGENT_DIR_NAME" = ".codex" ]; then
    python3 -c 'import json, sys; print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": sys.argv[1]}}, ensure_ascii=False))' "$message"
  else
    printf '%s\n' "$message"
  fi
}

if ! tts_enabled; then
  emit_context "[tts-config] TTS 음성 요약 끔. 이번 턴은 tts-summary.txt를 작성하지 않는다."
  exit 0
fi

case "$(printf '%s' "$TTS_VERBOSITY" | tr -d '[:space:]')" in
  1) DETAIL="1단계(한두 문장으로 결과만)" ;;
  3) DETAIL="3단계(근거, 트레이드오프, 후속 과제까지 상세히)" ;;
  *) DETAIL="2단계(작업 규모에 따라 2~10문장, 과정과 결정사항 포함)" ;;
esac
emit_context "[tts-config] TTS 음성 요약 켬, 상세 정도 $DETAIL. 글로벌 지침대로 tts-summary.txt를 작성한다."

exit 0
