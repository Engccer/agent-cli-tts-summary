#!/usr/bin/env python3
"""Windows 재생기(tts-replay.ps1)가 macOS 판과 같은 계약을 지키는지 검증한다.
PowerShell이 있는 환경(Windows)에서만 돌고, 없으면 건너뛴다.
실행: python scripts/test_tts_replay_windows.py
"""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "assets" / "windows"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


@unittest.skipUnless(POWERSHELL, "PowerShell이 없는 환경")
class WindowsTtsReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="tts-replay-win-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.hooks = self.home / "hooks"
        self.hooks.mkdir()
        for name in ("tts-config.ps1", "tts-replay.ps1"):
            shutil.copy(WINDOWS / name, self.hooks / name)
        self.agent = self.home / ".claude"
        self.wav_dir = self.agent / "TTS-Summary" / "wav"
        self.summary = self.agent / "tts-summary.txt"
        (self.agent / "TTS-Summary").mkdir(parents=True)

    def add_wav(self, name: str, age_seconds: int) -> Path:
        self.wav_dir.mkdir(parents=True, exist_ok=True)
        path = self.wav_dir / name
        path.write_bytes(b"RIFF")
        stamp = time.time() - age_seconds
        os.utime(path, (stamp, stamp))
        return path

    def run_replay(self, **extra_env: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, USERPROFILE=str(self.home), TTS_REPLAY_DRYRUN="1")
        env.pop("TTS_SUMMARY", None)
        env.update(extra_env)
        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.hooks / "tts-replay.ps1")],
            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_no_audio_reports_and_exits_zero(self) -> None:
        completed = self.run_replay()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("다시 재생할 요약 음성이 없습니다", completed.stdout)
        self.assertFalse(self.summary.exists())

    def test_plays_newest_and_blanks_summary(self) -> None:
        self.add_wav("tts-20260905-010137-0001.wav", age_seconds=600)
        newest = self.add_wav("tts-20260905-014849-0002.wav", age_seconds=10)
        completed = self.run_replay()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"file={newest}", completed.stdout)
        self.assertIn("직전 요약 음성(2026-09-05 01:48:49)을 다시 재생합니다.", completed.stdout)
        self.assertTrue(self.summary.exists())
        self.assertEqual(self.summary.read_text(encoding="utf-8").strip(), "")

    def test_muted_session_leaves_summary_file_alone(self) -> None:
        self.summary.write_text("코디네이터 요약", encoding="utf-8")
        self.add_wav("tts-20260905-014849-0002.wav", age_seconds=10)
        self.run_replay(TTS_SUMMARY="off")
        self.assertEqual(self.summary.read_text(encoding="utf-8"), "코디네이터 요약")


if __name__ == "__main__":
    unittest.main()
