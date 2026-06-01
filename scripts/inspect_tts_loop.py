#!/usr/bin/env python3
"""로컬 에이전트 CLI의 TTS 요약 루프 파일을 점검한다."""

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
        "note": "Antigravity는 .gemini 아래 Gemini 호환 파일을 공유하는 경우가 많으므로 gemini 항목도 함께 확인한다.",
    },
}


def newest_files(path: Path, pattern: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    files = [p for p in path.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size} for p in files[:10]]


def inspect_agent(root: Path, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    home = root / spec["home"]
    archive_txt = home / "TTS-Summary" / "txt"
    archive_wav = home / "TTS-Summary" / "wav"

    instruction_files = [home / rel for rel in spec.get("instructions", [])]
    config_files = [home / rel for rel in spec.get("configs", [])]
    hook_dirs = [home / rel for rel in spec.get("hook_dirs", [])]
    voice_files = sorted(home.glob("tts-*.txt")) if home.exists() else []

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
        if item["voice_rate_files"]:
            print("  음성/속도 파일:")
            for path in item["voice_rate_files"]:
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
