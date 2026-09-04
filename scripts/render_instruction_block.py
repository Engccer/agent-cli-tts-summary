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


def hooks_dir(agent: str, platform: str, home: str) -> str:
    """훅 스크립트 폴더. Windows는 hooks-windows(Gemini는 hooks), macOS는 Codex만 hooks-macos."""
    if platform == "windows":
        name = "hooks" if agent in ("gemini", "antigravity") else "hooks-windows"
        return f"{home}\\{name}"
    name = "hooks-macos" if agent == "codex" else "hooks"
    return f"{home}/{name}"


def render(agent: str, platform: str, home: str, language: str = "한국어") -> str:
    if platform == "macos":
        temp = f"{home}/tts-summary.txt"
        cfg = f"{home}/TTS-Summary/tts-config.txt"
        briefing = f'bash {hooks_dir(agent, platform, home)}/play-tts-briefing.sh "<보고문>"'
        briefing_en = f'bash {hooks_dir(agent, platform, home)}/play-tts-briefing.sh "<report>"'
    else:
        temp = f"{home}\\tts-summary.txt"
        cfg = f"{home}\\TTS-Summary\\tts-config.txt"
        briefing = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{hooks_dir(agent, platform, home)}\\play-tts-briefing.ps1" "<보고문>"'
        briefing_en = briefing.replace("<보고문>", "<report>")
    slash = " Claude Code 사용자는 `/tts`로도 바꾼다." if agent == "claude" else ""
    slash_en = " Claude Code users can also change them with `/tts`." if agent == "claude" else ""

    if is_korean(language):
        return f"""## TTS 요약 (ALWAYS)

매 턴 `[tts-config]` 줄이 알리는 대로 한다. 켬이면 응답을 마치기 전에 `{temp}`에 한국어 요약을 파일 편집 도구로 쓴다. 끔이면 쓰지 않는다. 줄이 없으면 켬, 3~6문장으로 본다.
- 요약 파일을 먼저 쓰고, 본문 답변을 턴의 마지막 출력으로 낸다. 본문 뒤에 도구 호출이 오면 본문이 화면에서 유실된다.
- 파일은 턴마다 새로 만든다. Stop hook이 읽은 뒤 삭제하므로 턴 시작 시점에는 없다.
- 분량은 `[tts-config]` 줄의 상세 정도를 따른다. 오류가 있었으면 반드시 넣는다.
- 사용자가 바로 듣는 브리핑체로 쓴다. 간접화법과 자기 인용("...를 설명했습니다")은 쓰지 않는다.
- 재생은 훅이 한다. TTS를 직접 호출하지 않는다. 긴 작업의 phase 전환 때만 `{briefing}`으로 1~2문장 보고한다.
- 설정 정본은 `{cfg}`(사용 여부·속도·상세 정도·선택지와 중간 보고 여부·프로바이더·음성)이며 바꾸면 다음 턴부터 적용된다.{slash}
- 병렬 작업 세션(런처가 `TTS_SUMMARY=off`로 띄운 세션)은 `[tts-config]` 줄이 끔을 알리며 요약을 쓰지 않는 것이 규칙이다. 그 세션에서 사용자에게 꼭 닿아야 하는 보고는 코디네이터 세션에 보낸다.
"""

    return f"""## TTS summary (ALWAYS)

Follow the `[tts-config]` line each turn. When it says on, write a summary in {language} to `{temp}` with a file editing tool before finishing the response. When it says off, do not write it. If the line is absent, assume on and 3-6 sentences.
- Write the summary file first, then emit the main answer as the turn's final output. A tool call after the answer pushes the answer off the screen.
- Create the file fresh every turn. The Stop hook deletes it after reading, so it does not exist when a turn starts.
- Match the length to the verbosity in the `[tts-config]` line. Always include errors.
- Write it as a briefing the user hears directly. No reported speech or self-quotation ("I explained ...").
- The hook plays the audio. Never invoke TTS yourself. Only at phase boundaries of long tasks, report 1-2 sentences with `{briefing_en}`.
- Settings live in `{cfg}` (on/off, speed, verbosity, interim announcements, provider, voice) and apply from the next turn.{slash_en}
- In a parallel worker session (launched with `TTS_SUMMARY=off`) the `[tts-config]` line says off and not writing the summary is the rule. Send anything the user must hear to the coordinator session instead.
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
