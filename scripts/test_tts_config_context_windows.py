#!/usr/bin/env python3
"""Windows 설정 통지의 Codex JSON·Claude 평문 및 매 호출 설정 갱신을 검증한다."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "assets" / "windows"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


@unittest.skipUnless(POWERSHELL, "PowerShell이 없는 환경")
class WindowsContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.hooks = self.home / "hooks"
        self.hooks.mkdir()
        shutil.copy2(WINDOWS / "tts-config.ps1", self.hooks)
        self.env = dict(os.environ, USERPROFILE=str(self.home))
        self.env.pop("TTS_SUMMARY", None)

    def run_hook(self, agent=".codex", config=None):
        source = (WINDOWS / "tts-config-context.ps1").read_text(encoding="utf-8-sig")
        source = source.replace('$AgentDirName = ".claude"', f'$AgentDirName = "{agent}"')
        script = self.hooks / "tts-config-context.ps1"
        script.write_text(source, encoding="utf-8-sig")
        config_dir = self.home / agent / "TTS-Summary"
        config_dir.mkdir(parents=True, exist_ok=True)
        if config is not None:
            (config_dir / "tts-config.txt").write_text(config, encoding="utf-8")
        summary = self.home / agent / "tts-summary.txt"
        summary.write_bytes(b"another session")
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            env=self.env, capture_output=True, encoding="utf-8-sig", check=True,
        )
        self.assertEqual(result.stderr, "")
        self.assertEqual(summary.read_bytes(), b"another session")
        return result.stdout.strip()

    def message(self, config=None):
        data = json.loads(self.run_hook(config=config))["hookSpecificOutput"]
        self.assertEqual(data["hookEventName"], "UserPromptSubmit")
        return data["additionalContext"]

    def test_codex_reads_changed_verbosity_each_call(self):
        for level in (1, 2, 3):
            self.assertIn(f"상세 정도 {level}단계", self.message(f"enabled=on\nverbosity={level}\n"))

    def test_codex_disabled_is_json(self):
        self.assertIn("쓰지 않는다", self.message("enabled=off\n"))

    def test_codex_muted_is_json_and_overrides_config(self):
        self.env["TTS_SUMMARY"] = "OFF"
        message = self.message("enabled=on\nverbosity=3\n")
        self.assertIn("쓰지 않는다", message)
        self.assertNotIn("상세 정도", message)

    def test_missing_config_defaults_to_level_two(self):
        self.assertIn("상세 정도 2단계", self.message())

    def test_claude_preserves_plain_text(self):
        for config in ("enabled=on\nverbosity=1\n", "enabled=off\n"):
            self.assertTrue(self.run_hook(".claude", config).startswith("[tts-config]"))


if __name__ == "__main__":
    unittest.main()
