#!/usr/bin/env python3
"""macOS Stop hook의 요약 누락 가드와 세션 음소거(TTS_SUMMARY=off) 계약을 검증한다.
재생 경로(say)까지 가지 않는 분기만 다루므로 소리가 나지 않는다.
실행: python scripts/test_stop_tts_mute.py
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
STOP_HOOK = ROOT / "assets" / "macos" / "stop-tts.sh"
AGENT_DIR_NAME = ".codex"  # 자산 템플릿의 기본값


class StopTtsMuteTests(unittest.TestCase):
    def run_hook(self, *, summary: str | None, session_env: dict[str, str], config: str = "enabled=on\n",
                 payload: str = "{}") -> tuple[subprocess.CompletedProcess, Path]:
        tmp = tempfile.mkdtemp()
        home = Path(tmp)
        agent_dir = home / AGENT_DIR_NAME
        (agent_dir / "TTS-Summary").mkdir(parents=True)
        (agent_dir / "TTS-Summary" / "tts-config.txt").write_text(config, encoding="utf-8")
        summary_file = agent_dir / "tts-summary.txt"
        if summary is not None:
            summary_file.write_text(summary, encoding="utf-8")
        env = os.environ.copy()
        env["HOME"] = str(home)
        env.pop("TTS_SUMMARY", None)
        env.update(session_env)
        completed = subprocess.run(
            ["bash", str(STOP_HOOK)], input=payload, capture_output=True, text=True, env=env,
        )
        return completed, summary_file

    def test_missing_summary_blocks_once_in_normal_session(self) -> None:
        """단독 세션 회귀: 요약이 없으면 exit 2로 한 번 되돌린다."""
        completed, _ = self.run_hook(summary=None, session_env={})
        self.assertEqual(completed.returncode, 2)
        self.assertIn("TTS 요약 누락", completed.stderr)

    def test_missing_summary_passes_after_retry(self) -> None:
        completed, _ = self.run_hook(summary=None, session_env={}, payload='{"stop_hook_active": true}')
        self.assertEqual(completed.returncode, 0)

    def test_muted_session_skips_guard(self) -> None:
        """병렬 작업 세션: 요약이 없어도 경고 없이 통과한다."""
        completed, _ = self.run_hook(summary=None, session_env={"TTS_SUMMARY": "off"})
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")

    def test_muted_session_leaves_other_sessions_summary_untouched(self) -> None:
        """병렬 작업 세션은 남의(코디네이터) 요약 파일을 읽지도 지우지도 않는다."""
        completed, summary_file = self.run_hook(summary="코디네이터 요약", session_env={"TTS_SUMMARY": "off"})
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(summary_file.read_text(encoding="utf-8"), "코디네이터 요약")
        self.assertFalse((summary_file.parent / "TTS-Summary" / "txt").exists())

    def test_blank_summary_skips_playback_silently(self) -> None:
        """공백뿐인 요약 파일(/tts-replay가 써 둔 것)은 보관도 가드도 없이 조용히 지우고 통과한다."""
        completed, summary_file = self.run_hook(summary="\n", session_env={})
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        self.assertFalse(summary_file.exists())
        self.assertFalse((summary_file.parent / "TTS-Summary" / "txt").exists())

    def test_disabled_config_still_clears_leftover(self) -> None:
        """설정 enabled=off는 종전대로 남은 요약을 치운다(세션 음소거와 다른 계약)."""
        completed, summary_file = self.run_hook(summary="남은 요약", session_env={}, config="enabled=off\n")
        self.assertEqual(completed.returncode, 0)
        self.assertFalse(summary_file.exists())


if __name__ == "__main__":
    unittest.main()
