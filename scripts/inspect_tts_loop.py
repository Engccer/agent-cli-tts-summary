#!/usr/bin/env python3
"""로컬 에이전트 CLI의 TTS 요약 루프 파일을 점검한다."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shlex
from pathlib import Path
from typing import Any


AGENTS = {
    "claude": {
        "home": ".claude",
        "instructions": ["CLAUDE.md"],
        "configs": ["settings.json", "settings.local.json"],
        "hook_dirs": ["hooks", "hooks-windows", "hooks-macos"],
    },
    "codex": {
        "home": ".codex",
        "instructions": ["AGENTS.md"],
        "configs": ["hooks.json", "config.toml"],
        "hook_dirs": ["hooks", "hooks-windows", "hooks-macos"],
    },
    "gemini": {
        "home": ".gemini",
        "instructions": ["GEMINI.md"],
        "configs": ["settings.json", "hooks.json", "config/hooks.json"],
        "hook_dirs": ["hooks", "hooks-windows", "hooks-macos"],
    },
    "antigravity": {
        "home": ".antigravitycli",
        "instructions": [],
        "configs": ["settings.json", "hooks.json", "config/hooks.json"],
        "hook_dirs": ["hooks"],
        "note": "Antigravity는 .gemini 아래 Gemini 호환 파일을 공유하는 경우가 많으므로 gemini 항목도 함께 확인한다.",
    },
}


CONFIG_KEYS = ("enabled", "speed", "verbosity", "interim", "provider",
               "voice_sapi", "voice_say", "voice_gemini", "voice_elevenlabs", "language_code")

def parse_config(path: Path) -> dict[str, str]:
    """TTS-Summary/tts-config.txt를 읽어 키=값을 돌려준다. 없거나 깨져 있으면 빈 dict."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().lower()
            if key in CONFIG_KEYS:
                values[key] = value.strip()
    except OSError:
        return {}
    return values


def newest_files(path: Path, pattern: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    files = [p for p in path.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size} for p in files[:10]]


def find_competing_consumers(
    root: Path,
    home: Path,
    launch_agent_dirs: list[Path] | None = None,
) -> tuple[list[str], list[str]]:
    """같은 요약을 감시하며 TTS 소비 명령을 실행하는 활성 LaunchAgent를 찾는다."""
    if launch_agent_dirs is None:
        launch_agent_dirs = [root / "Library" / "LaunchAgents"]
        if root == Path.home().resolve():
            launch_agent_dirs.append(Path("/Library/LaunchAgents"))

    summary_path = str(home / "tts-summary.txt")
    home_prefix = str(home) + "/"
    found: list[str] = []
    errors: list[str] = []
    for launch_agents in launch_agent_dirs:
        if not launch_agents.is_dir():
            continue
        for plist in sorted(launch_agents.glob("*.plist")):
            try:
                with plist.open("rb") as file:
                    payload = plistlib.load(file)
            except (OSError, plistlib.InvalidFileException, ValueError):
                errors.append(str(plist))
                continue
            if not isinstance(payload, dict) or payload.get("Disabled") is True:
                continue

            watch_paths = payload.get("WatchPaths", [])
            if not isinstance(watch_paths, list):
                watch_paths = []
            program_arguments = payload.get("ProgramArguments", [])
            if not isinstance(program_arguments, list):
                program_arguments = []
            program_values = [payload.get("Program"), *program_arguments]
            command_paths: list[str] = []
            for value in program_values:
                if not isinstance(value, str):
                    continue
                command_paths.append(value)
                try:
                    command_paths.extend(shlex.split(value))
                except ValueError:
                    pass
            watches_summary = summary_path in watch_paths
            runs_consumer = any(
                value.startswith(home_prefix)
                and (Path(value).name == "stop-tts.sh" or "tts_monitor" in Path(value).stem)
                for value in command_paths
            )
            if watches_summary and runs_consumer:
                found.append(str(plist))
    return found, errors


def inspect_agent(root: Path, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    home = root / spec["home"]
    archive_txt = home / "TTS-Summary" / "txt"
    archive_wav = home / "TTS-Summary" / "wav"

    instruction_files = [home / rel for rel in spec.get("instructions", [])]
    config_files = [home / rel for rel in spec.get("configs", [])]
    hook_dirs = [home / rel for rel in spec.get("hook_dirs", [])]
    config_path = home / "TTS-Summary" / "tts-config.txt"
    competing_consumers, consumer_inspection_errors = find_competing_consumers(root, home)

    return {
        "agent": name,
        "home": str(home),
        "home_exists": home.exists(),
        "note": spec.get("note", ""),
        "instructions": [str(p) for p in instruction_files if p.exists()],
        "configs": [str(p) for p in config_files if p.exists()],
        "hook_dirs": [str(p) for p in hook_dirs if p.exists()],
        "temp_summary": {
            "path": str(home / "tts-summary.txt"),
            "exists": (home / "tts-summary.txt").exists(),
            "size": (home / "tts-summary.txt").stat().st_size if (home / "tts-summary.txt").exists() else 0,
        },
        "archive_txt": {
            "path": str(archive_txt),
            "exists": archive_txt.exists(),
            "count": len(list(archive_txt.glob("*.txt"))) if archive_txt.exists() else 0,
            "newest": newest_files(archive_txt, "*.txt"),
        },
        "archive_wav": {
            "path": str(archive_wav),
            "exists": archive_wav.exists(),
            "count": len(list(archive_wav.glob("*.wav"))) if archive_wav.exists() else 0,
            "newest": newest_files(archive_wav, "*.wav"),
        },
        "config": {
            "path": str(config_path),
            "exists": config_path.is_file(),
            "values": parse_config(config_path),
        },
        "competing_consumers": competing_consumers,
        "consumer_inspection_errors": consumer_inspection_errors,
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"루트: {report['root']}")
    for item in report["agents"]:
        status = "OK" if item["home_exists"] else "MISS"
        print(f"\n[{status}] {item['agent']} -> {item['home']}")
        if item.get("note"):
            print(f"  참고: {item['note']}")
        print(f"  글로벌 지침: {len(item['instructions'])}")
        for path in item["instructions"]:
            print(f"    - {path}")
        print(f"  설정 파일: {len(item['configs'])}")
        for path in item["configs"]:
            print(f"    - {path}")
        print(f"  훅 폴더: {len(item['hook_dirs'])}")
        for path in item["hook_dirs"]:
            print(f"    - {path}")
        temp = item["temp_summary"]
        print(f"  임시 요약: {'있음' if temp['exists'] else '없음'} ({temp['size']} bytes) {temp['path']}")
        print(f"  TXT 보관: {item['archive_txt']['count']}개 {item['archive_txt']['path']}")
        print(f"  WAV 보관: {item['archive_wav']['count']}개 {item['archive_wav']['path']}")
        cfg = item["config"]
        if cfg["exists"]:
            shown = ", ".join(f"{k}={v}" for k, v in cfg["values"].items() if v) or "(값 없음)"
            print(f"  설정 파일: 있음 {cfg['path']}")
            print(f"    {shown}")
        else:
            print(f"  설정 파일: 없음 {cfg['path']} (assets의 tts-config.txt를 복사한다)")
        if item["competing_consumers"]:
            print("  경쟁 소비자 발견(Stop hook과 함께 쓰면 중복 재생·누락 요청 발생):")
            for path in item["competing_consumers"]:
                print(f"    - {path}")
        if item["consumer_inspection_errors"]:
            print("  LaunchAgent 검사 실패(수동 확인 필요):")
            for path in item["consumer_inspection_errors"]:
                print(f"    - {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path.home()), help="사용자 홈 루트. 생략 시 현재 사용자 홈. 예: C:/Users/이름 또는 /Users/name")
    parser.add_argument("--json", action="store_true", help="사람이 읽는 보고서 대신 JSON으로 출력")
    args = parser.parse_args()

    root = Path(os.path.expanduser(args.root)).resolve()
    report = {
        "root": str(root),
        "agents": [inspect_agent(root, name, spec) for name, spec in AGENTS.items()],
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
