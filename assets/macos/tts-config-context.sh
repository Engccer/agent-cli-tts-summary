#!/usr/bin/env bash
#
# UserPromptSubmit / PreInvocation hook (macOS) - TTS 설정의 사용 여부와 상세 정도를 에이전트에게 알린다.
# 재생은 Stop hook이 담당하고, 이 훅은 "요약을 쓸지, 얼마나 자세히 쓸지"만 전달한다.
# 설정을 바꾸면 다음 턴부터 바로 반영된다.
# 훅 payload(stdin)에 세션 식별자가 있으면 그 세션 전용 요약 파일 경로를 알려 준다. 같은 CLI를 여러
# 터미널에서 돌려도 세션끼리 요약을 덮어쓰지 않는다. 식별자를 모르면 공용 tts-summary.txt를 쓰게 한다.
# Claude에는 일반 텍스트를, Codex에는 hookSpecificOutput.additionalContext JSON을,
# Antigravity(.gemini, PreInvocation)에는 injectSteps.ephemeralMessage JSON을 출력한다.
#
# 이식 방법: AGENT_DIR_NAME 기본값을 대상 에이전트 폴더명으로 바꾼다(.claude / .codex / .gemini).
# 테스트나 임시 점검에서는 같은 이름의 환경 변수로 덮어쓸 수 있다.
#
set +e

AGENT_DIR_NAME="${AGENT_DIR_NAME:-.codex}"   # <-- 이식 시 기본값만 변경

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
[ "$AGENT_DIR_NAME" != ".claude" ] || AGENT_DIR="${CLAUDE_CONFIG_DIR:-$AGENT_DIR}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/tts-config.sh" 2>/dev/null || exit 0
tts_config_load "$AGENT_DIR"

# 손으로 실행해 stdin이 터미널이면 읽지 않는다(멈추지 않게).
HOOK_INPUT=""
[ -t 0 ] || HOOK_INPUT="$(cat 2>/dev/null)"

emit_context() {
  local message="$1"
  if [ "$AGENT_DIR_NAME" = ".codex" ]; then
    python3 -c 'import json, sys; print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": sys.argv[1]}}, ensure_ascii=False))' "$message"
  elif [ "$AGENT_DIR_NAME" = ".gemini" ]; then
    python3 -c 'import json, sys; print(json.dumps({"injectSteps": [{"ephemeralMessage": sys.argv[1]}]}, ensure_ascii=False))' "$message"
  else
    printf '%s\n' "$message"
  fi
}

if tts_session_muted; then
  emit_context "[tts-config] TTS 음성 요약 끔(병렬 작업 세션, TTS_SUMMARY=off). tts-summary.txt를 쓰지 않는다. 사용자에게 꼭 닿아야 하는 보고는 코디네이터 세션에 SendMessage로 보낸다."
  exit 0
fi

if ! tts_enabled; then
  emit_context "[tts-config] TTS 음성 요약 끔. tts-summary.txt를 쓰지 않는다."
  exit 0
fi

case "$(printf '%s' "$TTS_VERBOSITY" | tr -d '[:space:]')" in
  1) DETAIL="1단계(1~2문장, 결과만)" ;;
  3) DETAIL="3단계(7문장 이상, 근거·트레이드오프·후속 과제 포함)" ;;
  *) DETAIL="2단계(3~6문장, 과정과 결정 포함)" ;;
esac
SESSION_ID="$(tts_session_id "$HOOK_INPUT")"
if [ -n "$SESSION_ID" ]; then
  SESSION_FILE="$(tts_summary_file "$AGENT_DIR" "$SESSION_ID")"
  # 에이전트의 파일 쓰기 도구가 폴더 부재로 실패하지 않게 미리 만든다.
  # 아래 메시지의 변수는 중괄호로 감싼다(macOS 기본 bash 3.2는 뒤따르는 한글 바이트를 변수 이름에 붙여 읽는다).
  mkdir -p "${SESSION_FILE%/*}"
  if [ "$AGENT_DIR_NAME" = ".gemini" ]; then
    emit_context "[tts-config] TTS 음성 요약 켬, 상세 정도 $DETAIL. 응답을 마치기 전에 이 세션 전용 파일 ${SESSION_FILE}에 브리핑체 요약을 먼저 쓰고 본문 답변을 마지막으로 낸다."
  else
    emit_context "[tts-config] TTS 음성 요약 켬, 상세 정도 $DETAIL. 요약은 이 세션 전용 파일 ${SESSION_FILE}에 쓴다."
  fi
elif [ "$AGENT_DIR_NAME" = ".gemini" ]; then
  emit_context "[tts-config] TTS 음성 요약 켬, 상세 정도 $DETAIL. 응답을 마치기 전에 $AGENT_DIR/tts-summary.txt에 브리핑체 요약을 먼저 쓰고 본문 답변을 마지막으로 낸다."
else
  emit_context "[tts-config] TTS 음성 요약 켬, 상세 정도 $DETAIL. tts-summary.txt를 쓴다."
fi

exit 0
