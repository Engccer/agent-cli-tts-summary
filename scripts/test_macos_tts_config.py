#!/usr/bin/env python3
"""macOS TTS 속도 곡선과 ffmpeg 필터 계약을 검증한다."""

from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PARSER = ROOT / "assets" / "macos" / "tts-config.sh"


def speed_values(speed: str) -> tuple[str, str, str]:
    script = f"""
. {CONFIG_PARSER!s}
TTS_SPEED="$1"
printf '%s\n' "$(tts_tempo)" "$(tts_rate_wpm)" "$(tts_atempo_filter)"
"""
    completed = subprocess.run(
        ["bash", "-c", script, "tts-speed-test", speed],
        check=True,
        capture_output=True,
        text=True,
    )
    tempo, rate, atempo_filter = completed.stdout.splitlines()
    return tempo, rate, atempo_filter


class MacosTtsConfigTests(unittest.TestCase):
    def test_speed_curve_fixed_points(self) -> None:
        expected = {
            "5": ("1.00", "200", "atempo=1.0000"),
            "7.5": ("2.00", "400", "atempo=2.0000"),
            "10": ("4.00", "800", "atempo=2.0,atempo=2.0000"),
        }
        for speed, values in expected.items():
            with self.subTest(speed=speed):
                self.assertEqual(speed_values(speed), values)


if __name__ == "__main__":
    unittest.main()
