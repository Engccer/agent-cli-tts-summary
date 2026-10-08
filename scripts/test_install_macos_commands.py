"""macOS 공용 명령 설치의 보존, 격리, 명시적 훅 갱신 계약을 검증한다."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from install_macos_commands import COMMON_FILES, LAYOUTS, install


class MacOSCommandsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        for dirname, hooks, _ in LAYOUTS.values():
            base = self.home / dirname
            (base / "TTS-Summary").mkdir(parents=True)
            (base / "TTS-Summary/tts-config.txt").write_text("enabled=off\nspeed=7.5\nvoice_say=Minsu\n")
            (base / hooks).mkdir()
            (base / hooks / "stop-tts.sh").write_text("# previous hook\n")
            (base / "hooks.json").write_text('{"keep":true}\n')

    def test_all_agents_install_dependencies_and_preserve_settings_and_hooks(self):
        for agent, (dirname, hooks, skills) in LAYOUTS.items():
            with self.subTest(agent=agent):
                base = self.home / dirname
                config = (base / "TTS-Summary/tts-config.txt").read_bytes()
                self.assertTrue(install(self.home, agent))
                self.assertEqual(install(self.home, agent), [])
                self.assertEqual((base / "TTS-Summary/tts-config.txt").read_bytes(), config)
                self.assertEqual((base / "hooks.json").read_text(), '{"keep":true}\n')
                self.assertEqual((base / hooks / "stop-tts.sh").read_text(), "# previous hook\n")
                for name in COMMON_FILES:
                    self.assertTrue((base / hooks / name).is_file(), name)
                prefix = "codex-" if agent == "codex" else ""
                for name in ("tts-read", "tts-pause", "tts-replay"):
                    skill = (base / skills / f"{prefix}{name}" / "SKILL.md").read_text()
                    self.assertIn("tts-summary.txt", skill)
                    if agent != "claude":
                        self.assertNotIn("!`", skill)
                        self.assertIn(f"AGENT_DIR_NAME={dirname}", skill)

    def test_pause_default_is_agent_specific(self):
        for agent, (dirname, hooks, _) in LAYOUTS.items():
            with self.subTest(agent=agent):
                install(self.home, agent)
                env = dict(os.environ, HOME=str(self.home))
                env.pop("AGENT_DIR_NAME", None)
                env.pop("TTS_SUMMARY", None)
                result = subprocess.run(["bash", str(self.home / dirname / hooks / "tts-pause.sh")],
                                        env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                summary = self.home / dirname / "tts-summary.txt"
                self.assertEqual(summary.read_text().strip(), "")
                summary.unlink()
                for other, _, _ in LAYOUTS.values():
                    self.assertFalse((self.home / other / "tts-summary.txt").exists())

    def test_stop_update_requires_explicit_option_and_backs_up_original(self):
        for agent, (dirname, hooks, _) in LAYOUTS.items():
            with self.subTest(agent=agent):
                base = self.home / dirname
                install(self.home, agent, update_stop_hook=True)
                target = base / hooks / "stop-tts.sh"
                self.assertIn(f"${{AGENT_DIR_NAME:-{dirname}}}", target.read_text())
                backups = list((base / "backups").glob(f"tts-commands-*/{hooks}/stop-tts.sh"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_text(), "# previous hook\n")
                self.assertEqual(install(self.home, agent, update_stop_hook=True), [])

    def test_missing_config_fails_without_creating_default(self):
        config = self.home / ".gemini/TTS-Summary/tts-config.txt"
        config.unlink()
        with self.assertRaises(ValueError):
            install(self.home, "agy")
        self.assertFalse(config.exists())
        self.assertFalse((self.home / ".gemini/hooks/tts-read.sh").exists())

    def test_installed_read_uses_current_agent_transcript(self):
        fixtures = {
            "codex": (
                "sessions/rollout-test-read-session.jsonl", "CODEX_THREAD_ID",
                [
                    {"type": "session_meta", "payload": {"id": "read-session"}},
                    {"type": "turn_context", "payload": {"turn_id": "answer"}},
                    {"type": "response_item", "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "설명해 줘"}]}},
                    {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                     "phase": "final_answer", "content": [{"type": "output_text", "text": "Codex 응답입니다."}]}},
                    {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "answer"}},
                    {"type": "turn_context", "payload": {"turn_id": "read"}},
                    {"type": "response_item", "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "$codex-tts-read"}]}},
                ], "Codex 응답입니다."
            ),
            "agy": (
                "antigravity-cli/brain/read-session/.system_generated/logs/transcript_full.jsonl",
                "ANTIGRAVITY_CONVERSATION_ID",
                [
                    {"step_index": 0, "type": "USER_INPUT", "content": "설명해 줘"},
                    {"step_index": 1, "type": "PLANNER_RESPONSE", "source": "MODEL", "status": "DONE",
                     "content": "agy 응답입니다."},
                    {"step_index": 2, "type": "USER_INPUT", "content": "/tts-read"},
                ], "agy 응답입니다."
            ),
        }
        for agent, (relative, env_name, records, expected) in fixtures.items():
            with self.subTest(agent=agent):
                dirname, hooks, _ = LAYOUTS[agent]
                base = self.home / dirname
                transcript = base / relative
                transcript.parent.mkdir(parents=True)
                transcript.write_text("\n".join(json.dumps(row) for row in records) + "\n")
                install(self.home, agent)
                env = dict(os.environ, HOME=str(self.home), TTS_READ_DRYRUN="1")
                for key in ("AGENT_DIR_NAME", "TTS_SUMMARY", "CODEX_THREAD_ID", "CODEX_SESSION_ID",
                            "ANTIGRAVITY_CONVERSATION_ID"):
                    env.pop(key, None)
                env[env_name] = "read-session"
                result = subprocess.run(["bash", str(base / hooks / "tts-read.sh")],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)

    def test_symlink_skill_is_rejected_before_any_install(self):
        base = self.home / ".gemini"
        destination = self.home / "external"
        destination.mkdir()
        (base / "config").mkdir()
        (base / "config/skills").symlink_to(destination, target_is_directory=True)
        with self.assertRaises(ValueError):
            install(self.home, "agy")
        self.assertEqual(list(destination.iterdir()), [])
        self.assertFalse((base / "hooks/tts-config.sh").exists())

    def test_symlink_backup_directory_is_rejected_before_any_install(self):
        base = self.home / ".codex"
        destination = self.home / "external"
        destination.mkdir()
        (base / "backups").symlink_to(destination, target_is_directory=True)
        with self.assertRaises(ValueError):
            install(self.home, "codex", update_stop_hook=True)
        self.assertEqual(list(destination.iterdir()), [])
        self.assertFalse((base / "hooks-macos/tts-config.sh").exists())

    def test_parent_file_conflict_is_rejected_before_any_install(self):
        (self.home / ".gemini/config").write_text("keep")
        with self.assertRaises(ValueError):
            install(self.home, "agy")
        self.assertFalse((self.home / ".gemini/hooks/tts-config.sh").exists())


if __name__ == "__main__":
    unittest.main()
