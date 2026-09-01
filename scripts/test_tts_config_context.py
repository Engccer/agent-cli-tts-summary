#!/usr/bin/env python3
"""macOS 설정 통지 훅의 에이전트별 출력 계약을 검증한다."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_HOOK = ROOT / "assets" / "macos" / "tts-config-context.sh"


class TtsConfigContextTests(unittest.TestCase):
    def run_hook(self, agent_dir_name: str, config: str | None) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            if config is not None:
                config_dir = home / agent_dir_name / "TTS-Summary"
                config_dir.mkdir(parents=True)
                (config_dir / "tts-config.txt").write_text(config, encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["AGENT_DIR_NAME"] = agent_dir_name
            completed = subprocess.run(
                ["bash", str(CONTEXT_HOOK)],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            return completed.stdout.strip()

    def codex_message(self, config: str | None) -> str:
        payload = json.loads(self.run_hook(".codex", config))
        hook_output = payload["hookSpecificOutput"]
        self.assertEqual(hook_output["hookEventName"], "UserPromptSubmit")
        return hook_output["additionalContext"]

    def test_codex_emits_additional_context_json(self) -> None:
        self.assertIn(
            "상세 정도 3단계",
            self.codex_message("enabled=on\nverbosity=3\n"),
        )

    def test_codex_disabled_message_is_json(self) -> None:
        self.assertIn("TTS 음성 요약 끔", self.codex_message("enabled=off\n"))

    def test_codex_missing_config_uses_default_verbosity(self) -> None:
        self.assertIn("상세 정도 2단계", self.codex_message(None))

    def test_claude_keeps_plain_text_contract(self) -> None:
        output = self.run_hook(".claude", "enabled=on\nverbosity=1\n")
        self.assertTrue(output.startswith("[tts-config]"))
        self.assertIn("상세 정도 1단계", output)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(output)


if __name__ == "__main__":
    unittest.main()
