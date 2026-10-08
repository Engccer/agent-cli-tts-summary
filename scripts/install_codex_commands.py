#!/usr/bin/env python3
"""macOS Codex TTS 명령을 설치한다. 기존 설정과 훅 등록은 보존한다."""

import argparse
from pathlib import Path

from install_macos_commands import ROOT, install as install_macos


def install(home: Path) -> list[Path]:
    return install_macos(home, "codex")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="사용자 홈 또는 테스트용 홈")
    args = parser.parse_args()
    try:
        changed = install(args.home.expanduser().resolve())
    except (ValueError, OSError) as error:
        parser.exit(1, f"설치 실패: {error}\n")
    print(f"Codex TTS 명령 설치 완료: {len(changed)}개 파일 변경")
    print("새 Codex 세션의 /skills에서 codex-tts, codex-tts-replay, codex-tts-read, codex-tts-pause를 선택하세요.")


if __name__ == "__main__":
    main()
