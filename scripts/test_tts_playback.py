"""TTS 소유 프로세스 격리, 취소 경쟁 조건, 비동기 Stop hook를 무음 검증한다."""

import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("playback", ROOT / "assets/macos/tts_playback.py")
playback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(playback)


def wait_until(predicate, seconds=4):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.agent = self.home / ".claude"
        self.agent.mkdir()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(playback.pause, self.agent)

    def sleeping_command(self, marker):
        return [sys.executable, "-c", "import pathlib,time; pathlib.Path(" + repr(str(marker)) +
                ").write_text('started'); time.sleep(30)"]

    def jobs(self, agent=None):
        path = (agent or self.agent) / "TTS-Summary/playback/jobs.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def test_background_pause_only_stops_its_agent(self):
        other = self.home / ".codex"
        other.mkdir()
        self.addCleanup(playback.pause, other)
        first, second = self.home / "first", self.home / "second"
        playback.start(self.sleeping_command(first), self.agent, background=True, stdin=subprocess.DEVNULL)
        playback.start(self.sleeping_command(second), other, background=True, stdin=subprocess.DEVNULL)
        self.assertTrue(wait_until(lambda: first.exists() and second.exists()))
        self.assertEqual(playback.pause(self.agent), 1)
        self.assertEqual(self.jobs(), {})
        self.assertEqual(len(self.jobs(other)), 1)
        self.assertEqual(playback.pause(self.agent), 0)
        self.assertEqual(playback.pause(other), 1)

    def test_stale_registry_cannot_kill_unrelated_process(self):
        process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"], start_new_session=True)
        self.addCleanup(lambda: process.poll() is None and process.terminate())
        with playback.registry(self.agent) as jobs:
            jobs["a" * 32] = {"pid": process.pid, "launchd": False}
        self.assertEqual(playback.pause(self.agent), 0)
        self.assertIsNone(process.poll())
        process.terminate()
        process.wait(timeout=3)

    def test_worker_without_registered_token_cannot_start_late(self):
        marker = self.home / "late"
        result = playback.worker(self.sleeping_command(marker), self.agent, "b" * 32)
        self.assertEqual(result, 0)
        self.assertFalse(marker.exists())

    def test_completed_job_cleans_registry_and_new_job_after_pause_runs(self):
        playback.start([sys.executable, "-c", "pass"], self.agent)
        self.assertEqual(self.jobs(), {})
        playback.pause(self.agent)
        marker = self.home / "new"
        playback.start([sys.executable, "-c", "from pathlib import Path;Path(" + repr(str(marker)) + ").touch()"], self.agent)
        self.assertTrue(marker.exists())

    def test_pause_shell_suppresses_its_summary_but_muted_preserves_file(self):
        hooks = self.agent / "hooks"
        hooks.mkdir()
        for name in ("tts-pause.sh", "tts-config.sh", "tts_playback.py"):
            shutil.copy2(ROOT / "assets/macos" / name, hooks / name)
        summary = self.agent / "tts-summary.txt"
        summary.write_text("다른 세션 요약")
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=".claude", TTS_SUMMARY="off")
        result = subprocess.run(["bash", str(hooks / "tts-pause.sh")], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary.read_text(), "다른 세션 요약")
        env["TTS_SUMMARY"] = "on"
        subprocess.run(["bash", str(hooks / "tts-pause.sh")], env=env, capture_output=True, check=True)
        self.assertEqual(summary.read_text(), "\n")

    def test_pause_uses_custom_claude_home(self):
        custom = self.home / "custom-claude"
        custom.mkdir()
        self.addCleanup(playback.pause, custom)
        hooks = self.agent / "hooks"
        hooks.mkdir()
        for name in ("tts-pause.sh", "tts-config.sh", "tts_playback.py"):
            shutil.copy2(ROOT / "assets/macos" / name, hooks / name)
        marker = self.home / "custom-started"
        playback.start(self.sleeping_command(marker), custom, background=True, stdin=subprocess.DEVNULL)
        self.assertTrue(wait_until(marker.exists))
        result = subprocess.run(["bash", str(hooks / "tts-pause.sh")], capture_output=True, text=True,
                                env=dict(os.environ, HOME=str(self.home), CLAUDE_CONFIG_DIR=str(custom),
                                         AGENT_DIR_NAME=".claude", TTS_SUMMARY="on"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("중지했습니다", result.stdout)
        self.assertEqual(self.jobs(custom), {})
        self.assertEqual((custom / "tts-summary.txt").read_text(), "\n")
        self.assertFalse((self.agent / "tts-summary.txt").exists())

    @unittest.skipUnless(sys.platform == "darwin", "macOS launchd integration")
    def test_launchd_worker_is_cancellable_and_removes_private_request(self):
        marker = self.home / "launchd"
        started = time.monotonic()
        playback.start(self.sleeping_command(marker), self.agent, launchd=True, stdin=io.BytesIO(b""))
        self.assertLess(time.monotonic() - started, 3)
        self.assertTrue(wait_until(marker.exists))
        self.assertEqual(len(self.jobs()), 1)
        requests = list((self.agent / "TTS-Summary/playback").glob("*.json"))
        self.assertEqual([p.name for p in requests], ["jobs.json"])
        self.assertEqual(playback.pause(self.agent), 1)
        self.assertEqual(self.jobs(), {})

    @unittest.skipUnless(sys.platform == "darwin", "macOS launchd integration")
    def test_summary_hook_returns_before_playback_and_pause_prevents_fallback(self):
        hooks = self.agent / "hooks"
        hooks.mkdir()
        for name in ("stop-tts.sh", "tts-config.sh", "tts_playback.py"):
            shutil.copy2(ROOT / "assets/macos" / name, hooks / name)
        config = self.agent / "TTS-Summary"
        config.mkdir()
        (config / "tts-config.txt").write_text("enabled=on\nprovider=gemini-api\n")
        started, finished = self.home / "provider-started", self.home / "provider-finished"
        provider = hooks / "play-tts-gemini-api.sh"
        # 유료 호출 없이 합성이 진행 중인 작업을 재현. 실패 반환 뒤 fallback이 실행되면 안 된다.
        provider.write_text('#!/bin/bash\ntouch "$TTS_TEST_STARTED"\nsleep 30\ntouch "$TTS_TEST_FINISHED"\nexit 1\n')
        (self.agent / "tts-summary.txt").write_text("테스트용 요약")
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=".claude", TTS_SUMMARY="on",
                   TTS_TEST_STARTED=str(started), TTS_TEST_FINISHED=str(finished))
        before = time.monotonic()
        result = subprocess.run(["bash", str(hooks / "stop-tts.sh")], input="{}", env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(time.monotonic() - before, 3)
        self.assertTrue(wait_until(started.exists))
        self.assertEqual(playback.pause(self.agent), 1)
        time.sleep(.1)
        self.assertFalse(finished.exists())
        self.assertEqual(self.jobs(), {})
        self.assertFalse((self.agent / "tts-summary.txt").exists())


if __name__ == "__main__":
    unittest.main()
