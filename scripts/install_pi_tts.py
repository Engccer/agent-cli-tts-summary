#!/usr/bin/env python3
"""macOS pi에 음성 요약 확장을 설치한다. 기존 모델·설정 파일은 보존한다."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile

from install_macos_commands import ROOT, check_path

FILES = (
    "stop-tts.sh", "tts-config.sh", "tts-config-context.sh", "tts-config-set.sh",
    "tts_playback.py", "tts-replay.sh", "tts-pause.sh",
)


def install(home: Path, agent_dir: Path | None = None) -> list[Path]:
    home = home.expanduser().absolute()
    agent_dir = (agent_dir or home / ".pi/agent").expanduser().absolute()
    files = {}
    for name in FILES:
        data = (ROOT / "assets/macos" / name).read_bytes()
        if name.endswith(".sh"):
            # 실행 시 확장이 AGENT_DIR_NAME을 넘긴다. 기본 설치 경로도 pi로 맞춘다.
            for default in (".claude", ".codex"):
                data = data.replace(f"${{AGENT_DIR_NAME:-{default}}}".encode(),
                                    b"${AGENT_DIR_NAME:-.pi/agent}")
        files[agent_dir / "hooks" / name] = data
    files[agent_dir / "extensions/tts-summary.ts"] = (ROOT / "assets/pi/tts-summary.ts").read_bytes()
    config = agent_dir / "TTS-Summary/tts-config.txt"
    check_path(config, home)
    if not config.exists():
        files[config] = (ROOT / "assets/macos/tts-config.txt").read_bytes()
    elif not config.is_file():
        raise ValueError(f"설정 경로가 일반 파일이 아닙니다: {config}")
    backup_root = agent_dir / "backups"
    for target in [*files, backup_root]:
        check_path(target, home)
        if target.exists() and (not target.is_dir() if target == backup_root else not target.is_file()):
            raise ValueError(f"설치 경로 유형을 확인하세요: {target}")
        for parent in target.parents:
            if parent == home:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"상위 경로가 디렉터리가 아닙니다: {parent}")
    backup = None
    changed = []
    for target, data in files.items():
        mode = 0o755 if target.suffix == ".sh" else 0o644
        if target.exists() and target.read_bytes() == data and target.stat().st_mode & 0o777 == mode:
            continue
        if target.exists():
            backup_root.mkdir(parents=True, exist_ok=True)
            if backup is None:
                backup = Path(tempfile.mkdtemp(prefix="pi-tts-", dir=backup_root))
            saved = backup / target.relative_to(agent_dir)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".tts-install-", delete=False) as out:
            pending = Path(out.name)
            try:
                out.write(data)
                out.flush()
                pending.chmod(mode)
                pending.replace(target)
            finally:
                pending.unlink(missing_ok=True)
        changed.append(target)
    if backup:
        print(f"기존 파일 백업: {backup}")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--agent-dir", type=Path, default=os.environ.get("PI_CODING_AGENT_DIR"))
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.exit(1, "pi TTS 설치기는 macOS용입니다.\n")
    try:
        changed = install(args.home, args.agent_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, f"설치 실패: {error}\n")
    print(f"pi TTS 설치 완료: {len(changed)}개 파일 변경")
    print("pi 1.1.0 이상에서 /reload 또는 새 세션으로 적용하세요. /tts로 현재 설정을 확인합니다.")


if __name__ == "__main__":
    main()
