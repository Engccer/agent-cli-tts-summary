#!/usr/bin/env python3
"""Render a Korean global-instruction block for an agent TTS summary loop."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_HOME = {
    "windows": {
        "claude": r"C:\Users\pc\.claude",
        "codex": r"C:\Users\pc\.codex",
        "gemini": r"C:\Users\pc\.gemini",
        "antigravity": r"C:\Users\pc\.gemini",
    },
    "macos": {
        "claude": "~/.claude",
        "codex": "~/.codex",
        "gemini": "~/.gemini",
        "antigravity": "~/.gemini",
    },
}


def normalize_home(value: str) -> str:
    if value.startswith("~"):
        return value
    return str(Path(value))


def render(agent: str, platform: str, home: str) -> str:
    agent_label = {
        "claude": "Claude",
        "codex": "Codex",
        "gemini": "Gemini",
        "antigravity": "Antigravity",
    }[agent]
    temp = f"{home}/tts-summary.txt" if platform == "macos" else f"{home}\\tts-summary.txt"
    txt = f"{home}/TTS-Summary/txt/summary-*.txt" if platform == "macos" else f"{home}\\TTS-Summary\\txt\\summary-*.txt"
    wav = f"{home}/TTS-Summary/wav/tts-*.wav" if platform == "macos" else f"{home}\\TTS-Summary\\wav\\tts-*.wav"

    return f"""## **ALWAYS: TTS 요약 작성**

작업 완료 시 요약을 `{temp}`에 파일 편집으로 작성. 이 파일은 {agent_label} Stop hook 입력용 임시 파일이며, Stop hook이 자동으로 읽어 TTS 재생 후 보관본을 `{txt}`에 저장한다.
- WAV 보관 위치: `{wav}`
- TXT/WAV 모두 최신 10개만 유지
- Bash/PowerShell로 TTS를 직접 호출하지 않음
- TTS 요약은 자기 인용이나 간접화법을 사용하는 등의 메타적 서술을 피한다. 예: "사용자가 ...을 물었고 ...라고 답변했습니다", "...를 설명했습니다" 금지.
- 요약은 사용자가 바로 듣는 최종 브리핑처럼 직접 서술한다. 예: "...입니다", "...로 정리했습니다", "...을 수정했습니다" 형태를 사용.
- 간단한 작업 (파일 1~2개 수정): 2~3문장
- 중간 작업 (기능 구현, 여러 파일): 4~6문장 (과정 + 결정사항 포함)
- 복잡한 작업 (아키텍처 변경, 디버그): 7~10문장 (과정 + 결정사항 + 트레이드오프)
- 개발 작업이 아닌 일반 정보 정리·문서 작성·조사·브리핑 작업은 수정 파일 수가 아니라 응답의 길이와 정보량을 기준으로 요약 분량을 자연스럽게 조절한다.
- 에러 발생 시 반드시 포함.
- **언어:** 한국어
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=["claude", "codex", "gemini", "antigravity"], required=True)
    parser.add_argument("--platform", choices=["windows", "macos"], required=True)
    parser.add_argument("--home", help="Agent home folder. Defaults to the observed conventional path.")
    args = parser.parse_args()

    home = normalize_home(args.home or DEFAULT_HOME[args.platform][args.agent])
    print(render(args.agent, args.platform, home))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
