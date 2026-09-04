#!/usr/bin/env python3
"""Windows Stop hook(stop-tts.ps1)의 요약 누락 가드·세션 음소거·공백 요약 통과 계약을 macOS 판과 대칭으로 검증한다.
재생 경로까지 가지 않는 분기만 다루므로 소리가 나지 않는다. PowerShell이 있는 환경(Windows)에서만 돌고, 없으면 건너뛴다.
실행: python scripts/test_stop_tts_mute_windows.py
"""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "assets" / "windows"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
AGENT_DIR_NAME = ".codex"  # 자산 템플릿의 기본값


@unittest.skipUnless(POWERSHELL, "PowerShell이 없는 환경")
class WindowsStopTtsMuteTests(unittest.TestCase):
    def run_hook(self, *, summary: bytes | None, session_env: dict[str, str], config: str = "enabled=on\n",
                 payload: str = "{}") -> tuple[subprocess.CompletedProcess, Path]:
        home = Path(tempfile.mkdtemp(prefix="stop-tts-win-"))
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        hooks = home / "hooks"
        hooks.mkdir()
        for name in ("tts-config.ps1", "stop-tts.ps1"):
            shutil.copy(WINDOWS / name, hooks / name)
        agent_dir = home / AGENT_DIR_NAME
        (agent_dir / "TTS-Summary").mkdir(parents=True)
        (agent_dir / "TTS-Summary" / "tts-config.txt").write_text(config, encoding="utf-8")
        summary_file = agent_dir / "tts-summary.txt"
        if summary is not None:
            summary_file.write_bytes(summary)
        env = dict(os.environ, USERPROFILE=str(home))
        env.pop("TTS_SUMMARY", None)
        env.update(session_env)
        completed = subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(hooks / "stop-tts.ps1")],
            input=payload, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return completed, summary_file

    def test_missing_summary_blocks_once_in_normal_session(self) -> None:
        completed, _ = self.run_hook(summary=None, session_env={})
        self.assertEqual(completed.returncode, 2)
        self.assertIn("TTS 요약 누락", completed.stderr)

    def test_missing_summary_passes_after_retry(self) -> None:
        completed, _ = self.run_hook(summary=None, session_env={}, payload='{"stop_hook_active": true}')
        self.assertEqual(completed.returncode, 0)

    def test_muted_session_leaves_other_sessions_summary_untouched(self) -> None:
        completed, summary_file = self.run_hook(summary="코디네이터 요약".encode("utf-8"), session_env={"TTS_SUMMARY": "off"})
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(summary_file.read_text(encoding="utf-8"), "코디네이터 요약")

    def test_blank_summary_skips_playback_silently(self) -> None:
        """공백뿐인 요약 파일(/tts-replay가 써 둔 것)은 보관도 가드도 없이 조용히 지우고 통과한다."""
        for content in (b"\r\n", b""):
            with self.subTest(content=content):
                completed, summary_file = self.run_hook(summary=content, session_env={})
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stderr, "")
                self.assertFalse(summary_file.exists())
                self.assertFalse((summary_file.parent / "TTS-Summary" / "txt").exists())

    def test_disabled_config_still_clears_leftover(self) -> None:
        completed, summary_file = self.run_hook(summary="남은 요약".encode("utf-8"), session_env={}, config="enabled=off\n")
        self.assertEqual(completed.returncode, 0)
        self.assertFalse(summary_file.exists())


if __name__ == "__main__":
    unittest.main()
