#!/usr/bin/env python3
"""macOS Claude, Codex, agy의 TTS 명령을 설치하고 기존 설정과 훅 등록을 보존한다."""

import argparse
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = {
    "claude": (".claude", "hooks", "skills"),
    "codex": (".codex", "hooks-macos", "skills"),
    "agy": (".gemini", "hooks", "config/skills"),
}
COMMON_FILES = (
    "tts-config.sh", "tts-read.sh", "tts-read.py", "tts-pause.sh",
    "tts_playback.py", "tts_transcripts.py", "tts-replay.sh",
)


def check_path(target: Path, home: Path) -> None:
    for entry in (target, *target.parents):
        if entry == home:
            break
        if entry.is_symlink():
            raise ValueError(f"설치 대상 심볼릭 링크의 정본을 먼저 확인하세요: {entry}")


def install(home: Path, agent: str, *, update_stop_hook: bool = False) -> list[Path]:
    if agent not in LAYOUTS:
        raise ValueError(f"지원하지 않는 에이전트: {agent}")
    home = home.expanduser().absolute()
    dirname, hook_dir, skill_dir = LAYOUTS[agent]
    agent_dir = home / dirname
    if not (agent_dir / "TTS-Summary/tts-config.txt").is_file():
        raise ValueError(f"{agent} TTS 설정 파일이 없습니다. 기본 TTS 설정을 먼저 준비하세요.")
    names = list(COMMON_FILES)
    if agent == "codex":
        names.append("tts-config-set.sh")
    if update_stop_hook:
        names.append("stop-tts.sh")
    files = {}
    for name in names:
        data = (ROOT / "assets/macos" / name).read_bytes()
        if name.endswith(".sh"):
            for default in (".claude", ".codex"):
                data = data.replace(f"${{AGENT_DIR_NAME:-{default}}}".encode(), f"${{AGENT_DIR_NAME:-{dirname}}}".encode())
        files[agent_dir / hook_dir / name] = data
    skill_names = ("tts-read", "tts-pause", "tts-replay")
    if agent == "codex":
        skill_names = ("codex-tts", "codex-tts-replay", "codex-tts-read", "codex-tts-pause")
    for name in skill_names:
        if agent == "claude":
            source = ROOT / "assets/claude/skills" / name / "SKILL.md"
        elif agent == "codex":
            source = ROOT / "assets/codex" / name / "SKILL.md.in"
        else:
            source = ROOT / "assets/agy/skills" / name / "SKILL.md.in"
        files[agent_dir / skill_dir / name / "SKILL.md"] = source.read_bytes()

    # 파일과 백업 경로 전체를 검사한 뒤에만 쓰기를 시작한다.
    backup_root = agent_dir / "backups"
    check_path(backup_root, home)
    if backup_root.exists() and not backup_root.is_dir():
        raise ValueError(f"백업 경로가 디렉터리가 아닙니다: {backup_root}")
    for target in files:
        check_path(target, home)
        if target.exists() and not target.is_file():
            raise ValueError(f"설치 대상이 일반 파일이 아닙니다: {target}")
        for parent in target.parents:
            if parent == home:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"설치 상위 경로가 디렉터리가 아닙니다: {parent}")
    backup = None
    changed = []
    for target, data in files.items():
        mode = 0o755 if target.suffix == ".sh" else 0o644
        if target.exists() and target.read_bytes() == data and target.stat().st_mode & 0o777 == mode:
            continue
        if target.exists():
            if backup is None:
                backup_root.mkdir(exist_ok=True)
                backup = Path(tempfile.mkdtemp(prefix="tts-commands-", dir=backup_root))
            saved = backup / target.relative_to(agent_dir)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".tts-install-", delete=False) as output:
            pending = Path(output.name)
            try:
                output.write(data)
                output.flush()
                pending.chmod(mode)
                pending.replace(target)
            finally:
                pending.unlink(missing_ok=True)
        changed.append(target)
    if backup:
        print(f"기존 파일 백업: {backup}")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, choices=LAYOUTS)
    parser.add_argument("--home", type=Path, default=Path.home(), help="사용자 홈 또는 테스트용 홈")
    parser.add_argument("--update-stop-hook", action="store_true", help="기존 stop-tts.sh도 백업 후 갱신")
    args = parser.parse_args()
    try:
        changed = install(args.home, args.agent, update_stop_hook=args.update_stop_hook)
    except (ValueError, OSError) as error:
        parser.exit(1, f"설치 실패: {error}\n")
    print(f"{args.agent} TTS 명령 설치 완료: {len(changed)}개 파일 변경")
    if args.agent == "agy":
        print("agy에서 /skills reload 후 tts-read, tts-pause, tts-replay를 호출하세요.")
    elif args.agent == "codex":
        print("새 Codex 세션의 /skills에서 codex-tts-read, codex-tts-pause를 선택하세요.")
    else:
        print("Claude에서 /tts-read, /tts-pause, /tts-replay를 호출하세요.")


if __name__ == "__main__":
    main()
