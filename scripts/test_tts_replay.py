#!/usr/bin/env python3
"""macOS 재생기(tts-replay.sh)의 계약을 검증한다: 최신 음성 파일 선택, 이 턴의 요약 재생 억제(공백 요약 파일),
세션 음소거 시 요약 파일 불간섭, 파일 없음 시 exit 0. TTS_REPLAY_DRYRUN=1이라 소리는 나지 않는다.
실행: python scripts/test_tts_replay.py
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
REPLAY = ROOT / "assets" / "macos" / "tts-replay.sh"


class TtsReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="tts-replay-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
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

    def run_replay(self, **extra_env: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=".claude", TTS_REPLAY_DRYRUN="1")
        env.pop("TTS_SUMMARY", None)
        env.update(extra_env)
        return subprocess.run(["bash", str(REPLAY)], env=env, capture_output=True, text=True)

    def test_no_audio_reports_and_exits_zero(self) -> None:
        """파일이 없어도 exit 0. 0이 아니면 슬래시 명령 호출 자체가 중단된다."""
        completed = self.run_replay()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("다시 재생할 요약 음성이 없습니다", completed.stdout)
        self.assertFalse(self.summary.exists())

    def test_plays_newest_and_blanks_summary(self) -> None:
        self.add_wav("tts-20260905-010137.wav", age_seconds=600)
        newest = self.add_wav("tts-20260905-014849.wav", age_seconds=10)
        self.add_wav("tts-20260905-012942.aiff", age_seconds=300)
        completed = self.run_replay()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"file={newest}", completed.stdout)
        self.assertIn("직전 요약 음성(2026-09-05 01:48:49)을 다시 재생합니다.", completed.stdout)
        self.assertTrue(self.summary.exists())
        self.assertEqual(self.summary.read_text(encoding="utf-8").strip(), "")

    def test_plays_even_when_disabled(self) -> None:
        """사용자가 직접 청한 재생이라 enabled=off여도 튼다."""
        (self.agent / "TTS-Summary" / "tts-config.txt").write_text("enabled=off\n", encoding="utf-8")
        newest = self.add_wav("tts-20260905-014849.wav", age_seconds=10)
        completed = self.run_replay()
        self.assertIn(f"file={newest}", completed.stdout)

    def test_muted_session_leaves_summary_file_alone(self) -> None:
        """병렬 작업 세션은 재생만 하고 남의(코디네이터) 요약 파일에 손대지 않는다."""
        self.summary.write_text("코디네이터 요약", encoding="utf-8")
        newest = self.add_wav("tts-20260905-014849.wav", age_seconds=10)
        completed = self.run_replay(TTS_SUMMARY="off")
        self.assertIn(f"file={newest}", completed.stdout)
        self.assertEqual(self.summary.read_text(encoding="utf-8"), "코디네이터 요약")


if __name__ == "__main__":
    unittest.main()
