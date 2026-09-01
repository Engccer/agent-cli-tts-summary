#!/usr/bin/env python3
"""inspect_tts_loop.py의 경쟁 소비자 탐지 계약을 검증한다."""

from __future__ import annotations

import tempfile
import unittest
import plistlib
from pathlib import Path

from inspect_tts_loop import AGENTS, find_competing_consumers, inspect_agent


class InspectTtsLoopTests(unittest.TestCase):
    def test_codex_launch_agent_watching_summary_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".codex").mkdir()
            launch_agents = root / "Library" / "LaunchAgents"
            launch_agents.mkdir(parents=True)
            plist = launch_agents / "com.codex.tts-monitor.plist"
            plist.write_text(
                f"""<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
<key>WatchPaths</key><array><string>{root}/.codex/tts-summary.txt</string></array>
<key>ProgramArguments</key><array><string>{root}/.codex/hooks-macos/stop-tts.sh</string></array>
</dict></plist>
""",
                encoding="utf-8",
            )

            report = inspect_agent(root, "codex", AGENTS["codex"])

            self.assertEqual(report["competing_consumers"], [str(plist)])

    def test_unrelated_launch_agent_is_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".codex").mkdir()
            launch_agents = root / "Library" / "LaunchAgents"
            launch_agents.mkdir(parents=True)
            (launch_agents / "unrelated.plist").write_text(
                "<plist><dict><string>/tmp/unrelated</string></dict></plist>\n",
                encoding="utf-8",
            )

            report = inspect_agent(root, "codex", AGENTS["codex"])

            self.assertEqual(report["competing_consumers"], [])

    def test_disabled_launch_agent_is_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / ".codex"
            home.mkdir()
            launch_agents = root / "Library" / "LaunchAgents"
            launch_agents.mkdir(parents=True)
            plist = launch_agents / "disabled.plist"
            with plist.open("wb") as file:
                plistlib.dump(
                    {
                        "Disabled": True,
                        "WatchPaths": [str(home / "tts-summary.txt")],
                        "ProgramArguments": [str(home / "hooks-macos" / "stop-tts.sh")],
                    },
                    file,
                )

            report = inspect_agent(root, "codex", AGENTS["codex"])

            self.assertEqual(report["competing_consumers"], [])

    def test_description_text_alone_is_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / ".codex"
            home.mkdir()
            launch_agents = root / "Library" / "LaunchAgents"
            launch_agents.mkdir(parents=True)
            plist = launch_agents / "documentation.plist"
            with plist.open("wb") as file:
                plistlib.dump(
                    {
                        "Label": "example.documentation",
                        "Description": f"Do not run {home}/hooks-macos/stop-tts.sh for {home}/tts-summary.txt",
                        "ProgramArguments": ["/usr/bin/true"],
                    },
                    file,
                )

            report = inspect_agent(root, "codex", AGENTS["codex"])

            self.assertEqual(report["competing_consumers"], [])

    def test_binary_plist_with_non_ascii_home_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="사용자-") as temp_dir:
            root = Path(temp_dir)
            home = root / ".codex"
            home.mkdir()
            launch_agents = root / "Library" / "LaunchAgents"
            launch_agents.mkdir(parents=True)
            plist = launch_agents / "binary.plist"
            with plist.open("wb") as file:
                plistlib.dump(
                    {
                        "WatchPaths": [str(home / "tts-summary.txt")],
                        "ProgramArguments": ["/bin/zsh", str(home / "hooks-macos" / "stop-tts.sh")],
                    },
                    file,
                    fmt=plistlib.FMT_BINARY,
                )

            found, errors = find_competing_consumers(root, home)

            self.assertEqual(found, [str(plist)])
            self.assertEqual(errors, [])

    def test_explicit_system_launch_agent_directory_is_inspected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / ".codex"
            home.mkdir()
            system_launch_agents = root / "system-launch-agents"
            system_launch_agents.mkdir()
            plist = system_launch_agents / "system-monitor.plist"
            with plist.open("wb") as file:
                plistlib.dump(
                    {
                        "WatchPaths": [str(home / "tts-summary.txt")],
                        "ProgramArguments": [str(home / "hooks-macos" / "stop-tts.sh")],
                    },
                    file,
                )

            found, errors = find_competing_consumers(
                root,
                home,
                launch_agent_dirs=[system_launch_agents],
            )

            self.assertEqual(found, [str(plist)])
            self.assertEqual(errors, [])

    def test_invalid_plist_is_reported_as_inspection_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / ".codex"
            home.mkdir()
            launch_agents = root / "Library" / "LaunchAgents"
            launch_agents.mkdir(parents=True)
            plist = launch_agents / "broken.plist"
            plist.write_bytes(b"not a plist")

            found, errors = find_competing_consumers(root, home)

            self.assertEqual(found, [])
            self.assertEqual(errors, [str(plist)])

    def test_shell_command_string_running_stop_hook_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / ".codex"
            home.mkdir()
            launch_agents = root / "Library" / "LaunchAgents"
            launch_agents.mkdir(parents=True)
            plist = launch_agents / "shell-command.plist"
            hook = home / "hooks-macos" / "stop-tts.sh"
            with plist.open("wb") as file:
                plistlib.dump(
                    {
                        "WatchPaths": [str(home / "tts-summary.txt")],
                        "ProgramArguments": ["/bin/zsh", "-lc", f'bash "{hook}"'],
                    },
                    file,
                )

            found, errors = find_competing_consumers(root, home)

            self.assertEqual(found, [str(plist)])
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
