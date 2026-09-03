#!/usr/bin/env python3
"""macOS TTS 설정기(tts-config-set.sh)의 값 변경·검증·주석 보존 계약을 검증한다."""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETTER = ROOT / "assets" / "macos" / "tts-config-set.sh"
TEMPLATE = ROOT / "assets" / "macos" / "tts-config.txt"


class TtsConfigSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="tts-config-set-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        config_dir = self.home / ".claude" / "TTS-Summary"
        config_dir.mkdir(parents=True)
        self.config = config_dir / "tts-config.txt"
        shutil.copy(TEMPLATE, self.config)

    def run_setter(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=".claude")
        return subprocess.run(
            ["bash", str(SETTER), *args],
            env=env,
            capture_output=True,
            text=True,
        )

    def value(self, key: str) -> str:
        for line in self.config.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1]
        raise AssertionError(f"{key} 줄이 없다")

    def test_show_without_args(self) -> None:
        completed = self.run_setter()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("TTS 음성 요약 켬", completed.stdout)
        self.assertIn("속도 5(200wpm)", completed.stdout)
        self.assertIn("상세 2단계", completed.stdout)

    def test_toggle_and_set_values(self) -> None:
        self.assertEqual(self.run_setter("off").returncode, 0)
        self.assertEqual(self.value("enabled"), "off")
        self.assertEqual(self.run_setter("speed", "7.5").returncode, 0)
        self.assertEqual(self.value("speed"), "7.5")
        self.assertEqual(self.run_setter("verbosity", "3").returncode, 0)
        self.assertEqual(self.value("verbosity"), "3")
        completed = self.run_setter("on")
        self.assertEqual(self.value("enabled"), "on")
        self.assertIn("속도 7.5(400wpm), 상세 3단계", completed.stdout)

    def test_preserves_comments_and_other_keys(self) -> None:
        before = self.config.read_text(encoding="utf-8").splitlines()
        self.run_setter("speed", "8")
        after = self.config.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(before), len(after))
        changed = [(b, a) for b, a in zip(before, after) if b != a]
        self.assertEqual(changed, [("speed=5", "speed=8")])

    def test_rejects_invalid_values(self) -> None:
        for args in (("speed", "11"), ("speed", "abc"), ("speed", "0.5"),
                     ("verbosity", "4"), ("bogus",), ("on", "extra")):
            with self.subTest(args=args):
                completed = self.run_setter(*args)
                self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(self.value("speed"), "5")
        self.assertEqual(self.value("verbosity"), "2")
        self.assertEqual(self.value("enabled"), "on")

    def test_bom_first_line_is_updated_without_duplicate(self) -> None:
        self.config.write_bytes(b"\xef\xbb\xbfenabled=on\nspeed=5\nverbosity=2\n")
        for _ in range(3):
            self.assertEqual(self.run_setter("off").returncode, 0)
        lines = self.config.read_bytes().splitlines()
        self.assertEqual(lines, [b"enabled=off", b"speed=5", b"verbosity=2"])

    def test_crlf_lines_are_preserved(self) -> None:
        self.config.write_bytes(b"# \xec\xa3\xbc\xec\x84\x9d\r\nenabled=on\r\nspeed=5\r\n")
        self.assertEqual(self.run_setter("speed", "8").returncode, 0)
        self.assertEqual(self.config.read_bytes(),
                         b"# \xec\xa3\xbc\xec\x84\x9d\r\nenabled=on\r\nspeed=8\r\n")

    def test_single_quoted_argument_string_is_split(self) -> None:
        # 슬래시 명령은 "$ARGUMENTS" 한 덩어리로 넘긴다.
        self.assertEqual(self.run_setter("speed 8").returncode, 0)
        self.assertEqual(self.value("speed"), "8")
        completed = self.run_setter("")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("속도 8(460wpm)", completed.stdout)

    def test_interim_toggle(self) -> None:
        completed = self.run_setter("interim", "off")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.value("interim"), "off")
        self.assertIn("선택지·중간 보고 끔", completed.stdout)
        self.assertEqual(self.run_setter("interim", "on").returncode, 0)
        self.assertIn("선택지·중간 보고 켬", self.run_setter().stdout)
        self.assertNotEqual(self.run_setter("interim", "maybe").returncode, 0)
        self.assertEqual(self.value("interim"), "on")

    def test_appends_missing_key(self) -> None:
        self.config.write_text("# 주석만 있는 파일\nenabled=on\n", encoding="utf-8")
        self.run_setter("verbosity", "1")
        self.assertEqual(self.value("verbosity"), "1")
        self.assertEqual(self.value("enabled"), "on")


if __name__ == "__main__":
    unittest.main()
