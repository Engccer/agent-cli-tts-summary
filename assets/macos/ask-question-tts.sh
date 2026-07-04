#!/usr/bin/env bash
#
# ask-question-tts.sh (macOS)
#
# PreToolUse hook (matcher: AskUserQuestion).
# AskUserQuestion 도구 호출 직전 stdin의 tool_input(질문 JSON)을 읽어
# "질문 본문 + 선택지 라벨"을 한국어로 조립한 뒤 say로 백그라운드 재생한다.
#
# 이식 방법: AGENT_DIR_NAME 한 줄만 대상 에이전트 폴더명으로 바꾼다(.claude/.codex/.gemini).
# 음성/속도는 stop-tts.sh와 같은 tts-voice-say.txt / tts-rate-wpm.txt로 제어한다.
# 이 훅은 Stop hook의 self-contained 재생 방식(say 직접 호출)을 그대로 따라 외부 스크립트에
# 의존하지 않는다.
#
# 정책: 질문 + 선택지 라벨까지 읽고, 선택지 설명은 생략한다(스크린리더가 TUI 탐색 중
# 설명을 읽어주므로 중복을 피한다).
#
# 설계 원칙:
# - deterministic: 이미 구조화된 JSON을 읽어 발화하므로 LLM 추론이 필요 없다. 모델 협조 없이
#   도구 호출 시 항상 발동한다.
# - non-blocking: say를 백그라운드로 띄우고 즉시 exit 0 → 질문 TUI가 지연 없이 렌더된다.
# - 절대 차단하지 않음: 어떤 경우에도 exit 0. 파싱 실패해도 도구 호출을 막지 않는다.
#
# 디버그: ASK_TTS_DRYRUN=1 이면 발화 대신 조립된 문장을 stdout에 출력한다.

set +e

AGENT_DIR_NAME=".codex"   # <-- 이식 시 이 한 줄만 변경

AGENT_DIR="$HOME/$AGENT_DIR_NAME"
VOICE_FILE="$AGENT_DIR/tts-voice-say.txt"
RATE_FILE="$AGENT_DIR/tts-rate-wpm.txt"

HOOK_INPUT="$(cat 2>/dev/null)"
[ -z "$HOOK_INPUT" ] && exit 0

# 질문 JSON → 발화문 조립 (python3: 유니코드/구조 안전 처리)
SPEAK_TEXT="$(
  printf '%s' "$HOOK_INPUT" | python3 -c '
import json, sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

ti = data.get("tool_input", {}) or {}
questions = ti.get("questions", []) or []
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

[ -z "${SPEAK_TEXT//[[:space:]]/}" ] && exit 0

if [ "${ASK_TTS_DRYRUN:-0}" = "1" ]; then
  printf '%s\n' "$SPEAK_TEXT"
  exit 0
fi

# 음성/속도 옵션 구성 (stop-tts.sh와 동일한 파일 사용)
SAY_ARGS=()
[ -s "$VOICE_FILE" ] && SAY_ARGS+=(-v "$(cat "$VOICE_FILE")")
[ -s "$RATE_FILE" ] && SAY_ARGS+=(-r "$(cat "$RATE_FILE")")

# 백그라운드 재생 — 질문 TUI를 지연시키지 않는다. nohup으로 훅 종료 시 SIGHUP을 회피한다.
nohup say "${SAY_ARGS[@]}" "$SPEAK_TEXT" >/dev/null 2>&1 &

exit 0
