#!/usr/bin/env python3
"""macOS Codex TTS 명령을 설치한다. 기존 설정과 훅 등록은 보존한다."""

import argparse
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def install(home: Path) -> list[Path]:
    agent = home / ".codex"
    hooks = agent / "hooks-macos"
    if not (agent / "TTS-Summary/tts-config.txt").is_file():
        raise ValueError("Codex TTS 설정 파일이 없습니다. 기본 TTS 루프부터 설치하세요.")
    files = {}
    for name in ("tts-config-set.sh", "tts-replay.sh"):
        source = (ROOT / "assets/macos" / name).read_text()
        files[hooks / name] = source.replace(
            '${AGENT_DIR_NAME:-.claude}', '${AGENT_DIR_NAME:-.codex}'
        ).encode()
    parser = hooks / "tts-config.sh"
    files[parser] = (ROOT / "assets/macos/tts-config.sh").read_bytes()
    for name in ("codex-tts", "codex-tts-replay"):
        files[agent / "skills" / name / "SKILL.md"] = (
            ROOT / "assets/codex" / name / "SKILL.md.in"
        ).read_bytes()
    # 심볼릭 링크를 덮어쓰면 다른 정본을 수정할 수 있으므로 쓰기 전에 모두 확인한다.
    for target in files:
        for entry in (target, *target.parents):
            if entry == home:
                break
            if entry.is_symlink():
                raise ValueError(f"설치 대상 심볼릭 링크의 정본을 먼저 확인하세요: {entry}")
        if target.exists() and not target.is_file():
            raise ValueError(f"설치 대상이 일반 파일이 아닙니다: {target}")
    backup = None
    changed = []
    for target, data in files.items():
        if target.exists() and target.read_bytes() == data:
            continue
        if target.exists():
            if backup is None:
                (agent / "backups").mkdir(exist_ok=True)
                backup = Path(tempfile.mkdtemp(prefix="tts-commands-", dir=agent / "backups"))
            saved = backup / target.relative_to(agent)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if target.suffix == ".sh":
            target.chmod(0o755)
        changed.append(target)
    if backup:
        print(f"기존 파일 백업: {backup}")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="사용자 홈 또는 테스트용 홈")
    args = parser.parse_args()
    try:
        changed = install(args.home.expanduser().resolve())
    except (ValueError, OSError) as error:
        parser.exit(1, f"설치 실패: {error}\n")
    print(f"Codex TTS 명령 설치 완료: {len(changed)}개 파일 변경")
    print("새 Codex 세션에서 /skills → codex-tts 또는 codex-tts-replay를 선택하세요.")
    print("직접 호출: $codex-tts off / $codex-tts speed 8 / $codex-tts-replay")


if __name__ == "__main__":
    main()
