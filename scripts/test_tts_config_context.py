#!/usr/bin/env python3
"""macOS 설정 통지 훅의 에이전트별 출력 계약을 검증한다."""

from __future__ import annotations
import sys
import unittest

if sys.platform != "darwin":
    raise unittest.SkipTest("macOS 전용 스크립트를 실행하는 테스트다")


import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_HOOK = ROOT / "assets" / "macos" / "tts-config-context.sh"


class TtsConfigContextTests(unittest.TestCase):
    def run_hook(
        self,
        agent_dir_name: str,
        config: str | None,
        session_env: dict[str, str] | None = None,
        payload: str = "",
    ) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            if config is not None:
                config_dir = home / agent_dir_name / "TTS-Summary"
                config_dir.mkdir(parents=True)
                (config_dir / "tts-config.txt").write_text(config, encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["AGENT_DIR_NAME"] = agent_dir_name
            env.pop("TTS_SUMMARY", None)
            env.update(session_env or {})
            completed = subprocess.run(
                ["bash", str(CONTEXT_HOOK)],
                input=payload,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            return completed.stdout.strip()

    def codex_message(self, config: str | None, session_env: dict[str, str] | None = None) -> str:
        payload = json.loads(self.run_hook(".codex", config, session_env))
        hook_output = payload["hookSpecificOutput"]
        self.assertEqual(hook_output["hookEventName"], "UserPromptSubmit")
        return hook_output["additionalContext"]

    def agy_message(
        self,
        config: str | None,
        session_env: dict[str, str] | None = None,
        payload: str = '{"invocationNum": 1}',
    ) -> str:
        data = json.loads(self.run_hook(".gemini", config, session_env, payload=payload))
        return data["injectSteps"][0]["ephemeralMessage"]

    def test_codex_emits_additional_context_json(self) -> None:
        self.assertIn(
            "상세 정도 3단계",
            self.codex_message("enabled=on\nverbosity=3\n"),
        )

    def test_codex_disabled_message_is_json(self) -> None:
        self.assertIn("TTS 음성 요약 끔", self.codex_message("enabled=off\n"))

    def test_codex_missing_config_uses_default_verbosity(self) -> None:
        self.assertIn("상세 정도 2단계", self.codex_message(None))

    def test_agy_emits_inject_steps_ephemeral_message_with_summary_path(self) -> None:
        msg = self.agy_message("enabled=on\nverbosity=2\n")
        self.assertIn("[tts-config]", msg)
        self.assertIn("상세 정도 2단계", msg)
        self.assertIn("/.gemini/tts-summary.txt", msg)

    def test_agy_skips_subsequent_invocations_in_same_turn(self) -> None:
        output = self.run_hook(".gemini", "enabled=on\nverbosity=2\n", payload='{"invocationNum": 2}')
        self.assertEqual(json.loads(output), {})

    def test_claude_keeps_plain_text_contract(self) -> None:
        output = self.run_hook(".claude", "enabled=on\nverbosity=1\n")
        self.assertTrue(output.startswith("[tts-config]"))
        self.assertIn("상세 정도 1단계", output)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(output)

    def test_session_mute_env_overrides_enabled_config(self) -> None:
        """병렬 작업 세션(TTS_SUMMARY=off)은 설정이 켬이어도 쓰지 않는다고 알리고, 보고 경로를 함께 준다."""
        output = self.run_hook(".claude", "enabled=on\nverbosity=3\n", {"TTS_SUMMARY": "off"})
        self.assertTrue(output.startswith("[tts-config]"))
        self.assertIn("쓰지 않는다", output)
        self.assertIn("코디네이터", output)
        self.assertNotIn("상세 정도", output)
        self.assertIn("쓰지 않는다", self.codex_message("enabled=on\n", {"TTS_SUMMARY": "OFF"}))

    def test_session_mute_env_other_values_keep_config(self) -> None:
        output = self.run_hook(".claude", "enabled=on\nverbosity=1\n", {"TTS_SUMMARY": "on"})
        self.assertIn("상세 정도 1단계", output)


if __name__ == "__main__":
    unittest.main()
