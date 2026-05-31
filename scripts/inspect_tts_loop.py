#!/usr/bin/env python3
"""Inspect local agent CLI TTS summary loop files."""

from __future__ import annotations

import argparse
import json
import os
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
        "note": "Antigravity often shares Gemini-compatible files under .gemini; inspect gemini too.",
    },
}


def read_text(path: Path, limit: int = 512_000) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data[:limit].decode("utf-8", errors="ignore")


def newest_files(path: Path, pattern: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    files = [p for p in path.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size} for p in files[:10]]


def find_agentvibes_refs(paths: list[Path]) -> list[str]:
    refs: list[str] = []
    for base in paths:
        if base.is_file():
            candidates = [base]
        elif base.is_dir():
            candidates = [p for p in base.rglob("*") if p.is_file() and p.stat().st_size < 512_000]
        else:
            candidates = []
        for path in candidates:
            text = read_text(path)
            if "agentvibes" in text.lower():
                refs.append(str(path))
    return sorted(set(refs))


def inspect_agent(root: Path, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    home = root / spec["home"]
    archive_txt = home / "TTS-Summary" / "txt"
    archive_wav = home / "TTS-Summary" / "wav"
    paths_to_scan: list[Path] = []

    instruction_files = [home / rel for rel in spec.get("instructions", [])]
    config_files = [home / rel for rel in spec.get("configs", [])]
    hook_dirs = [home / rel for rel in spec.get("hook_dirs", [])]
    voice_files = sorted(home.glob("tts-*.txt")) if home.exists() else []

    paths_to_scan.extend(instruction_files)
    paths_to_scan.extend(config_files)
    paths_to_scan.extend(hook_dirs)

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
        "voice_rate_files": [str(p) for p in voice_files],
        "agentvibes_refs": find_agentvibes_refs(paths_to_scan),
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"Root: {report['root']}")
    for item in report["agents"]:
        status = "OK" if item["home_exists"] else "MISS"
        print(f"\n[{status}] {item['agent']} -> {item['home']}")
        if item.get("note"):
            print(f"  note: {item['note']}")
        print(f"  instructions: {len(item['instructions'])}")
        for path in item["instructions"]:
            print(f"    - {path}")
        print(f"  configs: {len(item['configs'])}")
        for path in item["configs"]:
            print(f"    - {path}")
        print(f"  hook dirs: {len(item['hook_dirs'])}")
        for path in item["hook_dirs"]:
            print(f"    - {path}")
        temp = item["temp_summary"]
        print(f"  temp summary: {'yes' if temp['exists'] else 'no'} ({temp['size']} bytes) {temp['path']}")
        print(f"  txt archive: {item['archive_txt']['count']} files {item['archive_txt']['path']}")
        print(f"  wav archive: {item['archive_wav']['count']} files {item['archive_wav']['path']}")
        if item["voice_rate_files"]:
            print("  voice/rate files:")
            for path in item["voice_rate_files"]:
                print(f"    - {path}")
        if item["agentvibes_refs"]:
            print("  AgentVibes text references:")
            for path in item["agentvibes_refs"]:
                print(f"    - {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path.home()), help="User home root, for example C:/Users/pc or /Users/name")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a human report")
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
