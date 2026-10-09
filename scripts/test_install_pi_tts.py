"""pi 설치의 설정 보존, 재설치, 백업과 경로 안전성을 검증한다."""
from pathlib import Path
import tempfile
import unittest

from install_pi_tts import FILES, install


class PiInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.agent = self.home / ".pi/agent"

    def test_install_and_reinstall_preserve_user_settings(self):
        self.agent.mkdir(parents=True)
        models = self.agent / "models.json"
        models.write_text('{"keep":true}')
        self.assertEqual(len(install(self.home)), len(FILES) + 2)
        config = self.agent / "TTS-Summary/tts-config.txt"
        config.write_text("enabled=off\nspeed=7.5\nvoice_say=Minsu\n")
        self.assertEqual(install(self.home), [])
        self.assertEqual(config.read_text(), "enabled=off\nspeed=7.5\nvoice_say=Minsu\n")
        self.assertEqual(models.read_text(), '{"keep":true}')
        self.assertFalse((self.home / ".codex").exists())
        self.assertFalse((self.agent / "settings.json").exists())

    def test_update_backs_up_changed_extension(self):
        install(self.home)
        target = self.agent / "extensions/tts-summary.ts"
        target.write_text("previous extension")
        self.assertEqual(install(self.home), [target])
        backups = list((self.agent / "backups").glob("pi-tts-*/extensions/tts-summary.ts"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "previous extension")

    def test_symlink_rejected_before_any_write(self):
        self.agent.mkdir(parents=True)
        elsewhere = self.home / "other"
        elsewhere.mkdir()
        (self.agent / "extensions").symlink_to(elsewhere)
        with self.assertRaises(ValueError):
            install(self.home)
        self.assertFalse((self.agent / "hooks").exists())
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_custom_agent_directory(self):
        custom = self.home / "custom pi"
        install(self.home, custom)
        self.assertTrue((custom / "extensions/tts-summary.ts").is_file())
        self.assertFalse(self.agent.exists())


if __name__ == "__main__":
    unittest.main()
