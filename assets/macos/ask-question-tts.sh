#!/usr/bin/env bash
#
# ask-question-tts.sh (macOS)
#
# PreToolUse hook. 선택 질문 도구 호출 직전 stdin의 tool_input(질문 JSON)을 읽어
# "질문 본문 + 선택지 라벨"을 조립한 뒤 비동기 재생한다. 설정의 provider를 최종 요약과 공유한다.
#
# matcher는 에이전트별 실제 도구명을 쓴다(다른 이름을 등록하면 절대 발동하지 않는다):
# - Claude Code: AskUserQuestion
# - Codex CLI: request_user_input
# - Antigravity CLI (agy): ask_question
# 세 도구의 질문 payload(tool_input.questions 또는 toolCall.args.questions, options[].label 또는 문자열 배열)를
# 이 스크립트 하나가 모두 처리한다. "기타 직접 입력" 안내도 세 도구 모두 참이다.
# Antigravity PreToolUse는 stdout으로 {"decision":"allow"} JSON을 요구하므로(ASK_TTS_DRYRUN 제외) 마지막에 출력한다.
#
# 이식 방법: AGENT_DIR_NAME 한 줄만 대상 에이전트 폴더명으로 바꾼다(.claude/.codex/.gemini).
# provider·음성·속도는 stop-tts.sh와 같은 TTS-Summary/tts-config.txt로 제어하고,
# interim=off면 응답 완료 요약만 남기고 이 안내는 하지 않는다.
# 재생은 play-tts-briefing.sh → tts_playback.py → stop-tts.sh --speak 경로를 공유한다.
#
# 정책: 질문 + 선택지 라벨까지 읽고, 선택지 설명은 생략한다(스크린리더가 TUI 탐색 중
# 설명을 읽어주므로 중복을 피한다).
#
# 설계 원칙:
# - deterministic: 이미 구조화된 JSON을 읽어 발화하므로 LLM 추론이 필요 없다. 모델 협조 없이
#   도구 호출 시 항상 발동한다.
# - non-blocking: 공용 worker를 launchd 일회성 작업으로 띄우고 바로 끝난다.
# - 절대 차단하지 않음: 어떤 경우에도 exit 0. 파싱 실패해도 도구 호출을 막지 않는다.
#
# 디버그: ASK_TTS_DRYRUN=1 이면 발화 대신 조립된 문장을 stdout에 출력한다.

set +e

AGENT_DIR_NAME="${AGENT_DIR_NAME:-.codex}"   # <-- 이식 시 기본값 변경

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
[ "$AGENT_DIR_NAME" != ".claude" ] || AGENT_DIR="${CLAUDE_CONFIG_DIR:-$AGENT_DIR}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

finish_hook() {
  [ "$AGENT_DIR_NAME" = ".gemini" ] && [ "${ASK_TTS_DRYRUN:-0}" != "1" ] && printf '{"decision":"allow"}\n'
  exit 0
}

# 설정은 발화 여부(enabled·interim·세션 음소거) 판정에만 쓴다. 음성은 stop-tts.sh가 고른다.
. "$SCRIPT_DIR/tts-config.sh"
tts_config_load "$AGENT_DIR"
tts_session_muted && finish_hook
tts_enabled || finish_hook
tts_interim_enabled || finish_hook

HOOK_INPUT="$(cat 2>/dev/null)"
[ -z "$HOOK_INPUT" ] && finish_hook

# 질문 JSON → 발화문 조립 (python3: 유니코드/구조 안전 처리)
SPEAK_TEXT="$(
  printf '%s' "$HOOK_INPUT" | python3 -c '
import json, sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

ti = data.get("tool_input") or ((data.get("toolCall") or {}).get("args") if isinstance(data.get("toolCall"), dict) else None) or {}
questions = ti.get("questions", []) if isinstance(ti, dict) else []
if not isinstance(questions, list):
    sys.exit(0)

parts = []
multi = len(questions) > 1
for i, q in enumerate(questions, 1):
    if not isinstance(q, dict):
        continue
    qtext = (q.get("question") or q.get("header") or "").strip()
    if not qtext:
        continue
    labels = []
    for opt in (q.get("options") or []):
        if isinstance(opt, dict):
            lab = (opt.get("label") or "").strip()
        elif isinstance(opt, str):
            lab = opt.strip()
        else:
            lab = ""
        if lab:
            labels.append(lab)
    prefix = f"{i}번 질문: " if multi else "질문: "
    seg = prefix + qtext
    # "기타" 직접 입력 옵션은 항상 자동 제공되므로 안내에 덧붙인다.
    if labels:
        seg += " 선택지는 " + ", ".join(labels) + ", 그리고 기타 직접 입력입니다."
    parts.append(seg)

if not parts:
    sys.exit(0)

print("  ".join(parts))
'
)"

[ -z "${SPEAK_TEXT//[[:space:]]/}" ] && finish_hook

if [ "${ASK_TTS_DRYRUN:-0}" = "1" ]; then
  printf '%s\n' "$SPEAK_TEXT"
  exit 0
fi

# stdout은 Antigravity의 allow JSON 전용이므로 재생 쪽 출력은 버린다.
AGENT_DIR_NAME="$AGENT_DIR_NAME" bash "$SCRIPT_DIR/play-tts-briefing.sh" "$SPEAK_TEXT" >/dev/null 2>&1
finish_hook
