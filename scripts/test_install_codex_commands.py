"""설치된 명령의 에이전트 격리, 설정 보존과 재생 계약을 검증한다."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from install_codex_commands import ROOT, install


class CodexCommandsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.agent = self.home / ".codex"
        self.config = self.agent / "TTS-Summary/tts-config.txt"
        self.config.parent.mkdir(parents=True)
        self.original = b"# keep\nenabled=off\nspeed=7.5\nverbosity=1\nprovider=say\n"
        self.config.write_bytes(self.original)
        self.claude = self.home / ".claude/TTS-Summary/tts-config.txt"
        self.claude.parent.mkdir(parents=True)
        self.claude.write_bytes(b"enabled=on\nspeed=2\n")

    def run_command(self, name, *args, **extra):
        env = dict(os.environ, HOME=str(self.home), TTS_REPLAY_DRYRUN="1")
        env.pop("AGENT_DIR_NAME", None)
        env.pop("TTS_SUMMARY", None)
        env.update(extra)
        return subprocess.run(["bash", str(self.agent / "hooks-macos" / name), *args],
                              env=env, text=True, capture_output=True)

    def test_install_preserves_config_and_is_idempotent(self):
        self.assertEqual(len(install(self.home)), 5)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertEqual(install(self.home), [])
        self.assertFalse((self.agent / "hooks.json").exists())

    def test_installed_setter_changes_codex_only_and_rejects_invalid_input(self):
        install(self.home)
        for args in (("on",), ("speed", "8"), ("verbosity", "2"), ("interim", "off"), ("off",)):
            result = self.run_command("tts-config-set.sh", *args)
            self.assertEqual(result.returncode, 0, result.stderr)
        before = self.config.read_bytes()
        self.assertIn(b"speed=8", before)
        self.assertNotEqual(self.run_command("tts-config-set.sh", "speed", "11").returncode, 0)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.claude.read_bytes(), b"enabled=on\nspeed=2\n")

    def test_replay_uses_codex_archive_and_suppresses_new_summary(self):
        install(self.home)
        archive = self.agent / "TTS-Summary/wav"
        archive.mkdir()
        audio = archive / "tts-20260907-120000.wav"
        audio.write_bytes(b"RIFF")
        result = self.run_command("tts-replay.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"file={audio}", result.stdout)
        self.assertEqual((self.agent / "tts-summary.txt").read_text().strip(), "")
        self.assertFalse((self.home / ".claude/tts-summary.txt").exists())

    def test_updates_back_up_existing_command(self):
        install(self.home)
        target = self.agent / "skills/codex-tts/SKILL.md"
        target.write_text("previous")
        install(self.home)
        backups = list((self.agent / "backups").glob("tts-commands-*/skills/codex-tts/SKILL.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "previous")

    def test_empty_archive_does_not_trigger_stop_missing_summary_guard(self):
        install(self.home)
        self.config.write_text("enabled=on\n")
        result = self.run_command("tts-replay.sh")
        self.assertIn("다시 재생할 요약 음성이 없습니다", result.stdout)
        stop = subprocess.run(
            ["bash", str(ROOT / "assets/macos/stop-tts.sh")],
            env=dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=".codex", TTS_SUMMARY="on"),
            input='{"stop_hook_active":false}', text=True, capture_output=True,
        )
        self.assertEqual(stop.returncode, 0, stop.stderr)

    def test_upgrades_old_parser_and_muted_replay_leaves_summary_alone(self):
        hooks = self.agent / "hooks-macos"
        hooks.mkdir()
        (hooks / "tts-config.sh").write_text("# old parser\n")
        install(self.home)
        archive = self.agent / "TTS-Summary/wav"
        archive.mkdir()
        (archive / "tts-20260907-120000.wav").write_bytes(b"RIFF")
        summary = self.agent / "tts-summary.txt"
        summary.write_text("other session")
        result = self.run_command("tts-replay.sh", TTS_SUMMARY="off")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(summary.read_text(), "other session")

    def test_symlink_target_is_rejected_before_writes(self):
        hooks = self.agent / "hooks-macos"
        hooks.mkdir()
        (hooks / "tts-replay.sh").symlink_to(self.claude)
        with self.assertRaises(ValueError):
            install(self.home)
        self.assertFalse((hooks / "tts-config-set.sh").exists())


if __name__ == "__main__":
    unittest.main()
