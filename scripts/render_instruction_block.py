#!/usr/bin/env python3
"""에이전트 TTS 요약 루프용 한국어 글로벌 지침 블록을 출력한다."""

from __future__ import annotations

import argparse
from pathlib import Path


# 에이전트별 홈 폴더명. Antigravity는 보통 .gemini를 공유한다.
AGENT_DIRNAME = {
    "claude": ".claude",
    "codex": ".codex",
    "gemini": ".gemini",
    "antigravity": ".gemini",
}

# 이 값들 중 하나면 한국어 블록을 쓴다. 그 외 언어는 영어 블록에 언어명을 지정해 출력한다
# (임의 언어로 블록 전체를 번역할 수는 없으므로, 규칙은 영어로 쓰고 요약 언어만 지정한다).
KOREAN_ALIASES = {"ko", "kor", "korean", "ko-kr", "한국어"}


def is_korean(language: str) -> bool:
    return language.strip().lower() in KOREAN_ALIASES


def default_home(platform: str, agent: str) -> str:
    """현재 사용자 홈을 기준으로 기본 에이전트 홈 경로를 만든다(개인 경로 하드코딩 회피)."""
    dirname = AGENT_DIRNAME[agent]
    if platform == "macos":
        return f"~/{dirname}"
    return str(Path.home() / dirname)


def normalize_home(value: str) -> str:
    if value.startswith("~"):
        return value
    return str(Path(value))


def render(agent: str, platform: str, home: str, language: str = "한국어") -> str:
    agent_label = {
        "claude": "Claude",
        "codex": "Codex",
        "gemini": "Gemini",
        "antigravity": "Antigravity",
    }[agent]
    temp = f"{home}/tts-summary.txt" if platform == "macos" else f"{home}\\tts-summary.txt"
    txt = f"{home}/TTS-Summary/txt/summary-*.txt" if platform == "macos" else f"{home}\\TTS-Summary\\txt\\summary-*.txt"
    wav = f"{home}/TTS-Summary/wav/tts-*.wav" if platform == "macos" else f"{home}\\TTS-Summary\\wav\\tts-*.wav"

    if is_korean(language):
        return f"""## **ALWAYS: TTS 요약 작성**

작업 완료 시 요약을 `{temp}`에 파일 편집으로 작성. 이 파일은 {agent_label} Stop hook 입력용 임시 파일이며, Stop hook이 자동으로 읽어 TTS 재생 후 보관본을 `{txt}`에 저장한다.
- **순서 필수: 요약 파일을 먼저 쓰고, 본문 답변을 턴의 마지막 출력으로 낸다.** 본문 뒤에 요약 쓰기(또는 어떤 도구 호출)가 오면 본문이 도구 호출 사이 텍스트로 밀려 화면에서 유실된다.
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

    return f"""## **ALWAYS: Write the TTS summary**

When you finish a task, write a summary to `{temp}` with a file editing tool. This file is a temporary input for the {agent_label} Stop hook, which reads it automatically, plays it as speech, and archives a copy under `{txt}`.
- **Order matters: write the summary file first, then emit the main answer as the turn's final output.** If the summary write (or any tool call) comes after the main answer, the answer is pushed into between-tool-call text and lost from the screen.
- WAV archive location: `{wav}`
- Only the 10 most recent TXT/WAV files are kept
- Never invoke TTS directly from Bash/PowerShell
- Avoid meta narration such as self-quotation or reported speech. Do not write "The user asked ... and I answered ..." or "I explained ...".
- Write the summary as a final briefing the user hears directly, e.g. "Fixed ...", "Organized ... into ...".
- Simple task (1-2 files changed): 2-3 sentences
- Medium task (feature work, several files): 4-6 sentences (process + decisions)
- Complex task (architecture change, debugging): 7-10 sentences (process + decisions + trade-offs)
- For non-development work (research, writing, organizing information, briefings), scale the summary to the length and information density of the response rather than the number of files changed.
- Always include errors when they occurred.
- **Language:** {language}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=["claude", "codex", "gemini", "antigravity"], required=True)
    parser.add_argument("--platform", choices=["windows", "macos"], required=True)
    parser.add_argument("--home", help="에이전트 홈 폴더. 생략하면 관찰된 기본 경로를 사용한다.")
    parser.add_argument(
        "--language",
        default="한국어",
        help='TTS 요약 언어. 기본값 한국어. 한국어(ko/korean/한국어)면 한국어 블록을, '
             '그 외 값(예: "English", "日本語")이면 영어 블록에 해당 언어를 지정해 출력한다.',
    )
    args = parser.parse_args()

    home = normalize_home(args.home or default_home(args.platform, args.agent))
    print(render(args.agent, args.platform, home, args.language))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
