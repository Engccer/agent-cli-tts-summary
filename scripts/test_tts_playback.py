"""TTS 소유 프로세스 격리, 취소 경쟁 조건, 비동기 Stop hook를 무음 검증한다."""

import sys
import unittest

if sys.platform != "darwin":
    raise unittest.SkipTest("macOS 전용 스크립트를 실행하는 테스트다")

import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import signal
import time
import unittest
from unittest.mock import patch

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
        # 재생 큐 잠금을 시험용 파일로 돌린다. 실제 사용자 잠금에 줄을 서지 않는다.
        self.lock = self.home / "playback.lock"
        environment = patch.dict(os.environ, {"TTS_PLAYBACK_LOCK": str(self.lock)})
        environment.start()
        self.addCleanup(environment.stop)
        # 시험을 돌리는 CLI 세션의 식별자가 공백 억제 파일의 자리를 바꾸지 않게 한다.
        for name in ("CLAUDE_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "ANTIGRAVITY_CONVERSATION_ID"):
            os.environ.pop(name, None)

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

    def other_agent(self, name=".codex"):
        other = self.home / name
        other.mkdir()
        self.addCleanup(playback.pause, other)
        return other

    def timed_command(self, log, name, seconds=0.5):
        code = ("import sys,time\nlog,name,seconds=sys.argv[1],sys.argv[2],float(sys.argv[3])\n"
                "open(log,'a').write(f'start {name} {time.time()}\\n')\ntime.sleep(seconds)\n"
                "open(log,'a').write(f'end {name} {time.time()}\\n')\n")
        return [sys.executable, "-c", code, str(log), name, str(seconds)]

    def test_queue_lock_path_is_per_user_and_overridable(self):
        self.assertEqual(playback.queue_lock_path({"HOME": "/tmp/tts-home"}),
                         Path("/tmp/tts-home/Library/Caches/agent-cli-tts-summary/playback.lock"))
        self.assertEqual(playback.queue_lock_path({"HOME": "/tmp/tts-home", "TTS_PLAYBACK_LOCK": "/tmp/x.lock"}),
                         Path("/tmp/x.lock"))

    def test_queued_jobs_of_different_agents_run_one_after_another(self):
        other = self.other_agent()
        log = self.home / "order.log"
        for name, agent in (("first", self.agent), ("second", other), ("third", self.agent)):
            playback.start(self.timed_command(log, name), agent, background=True,
                           stdin=subprocess.DEVNULL, queue=True)
            if name == "first":  # 먼저 시작한 작업이 잠금을 쥔 뒤에 다음 작업을 넣는다.
                self.assertTrue(wait_until(lambda: log.exists()))
        self.assertTrue(wait_until(lambda: log.exists() and log.read_text().count("end ") == 3, seconds=10))
        events = [line.split() for line in log.read_text().splitlines()]
        self.assertEqual(events[0][:2], ["start", "first"])
        # 시작과 끝이 번갈아 나오고, 각 끝은 바로 앞에서 시작한 작업의 것이다(겹치지 않음).
        self.assertEqual([event[0] for event in events], ["start", "end"] * 3)
        for begin, finish in zip(events[::2], events[1::2]):
            self.assertEqual(begin[1], finish[1])
        self.assertTrue(wait_until(lambda: self.jobs() == {} and self.jobs(other) == {}))

    def test_job_without_queue_ignores_the_lock(self):
        other = self.other_agent()
        holder, free = self.home / "holder", self.home / "free"
        playback.start(self.sleeping_command(holder), other, background=True, stdin=subprocess.DEVNULL, queue=True)
        self.assertTrue(wait_until(holder.exists))
        playback.start(self.sleeping_command(free), self.agent, background=True, stdin=subprocess.DEVNULL)
        self.assertTrue(wait_until(free.exists), "미리 합성처럼 --queue 없는 작업은 재생 중에도 돈다")

    def test_pause_stops_waiting_job_and_dead_holder_releases_queue(self):
        other = self.other_agent()
        holder, waiting, next_job = self.home / "holder", self.home / "waiting", self.home / "next"
        playback.start(self.sleeping_command(holder), other, background=True, stdin=subprocess.DEVNULL, queue=True)
        self.assertTrue(wait_until(holder.exists))
        playback.start(self.sleeping_command(waiting), self.agent, background=True, stdin=subprocess.DEVNULL, queue=True)
        self.assertTrue(wait_until(lambda: any(job["pid"] for job in self.jobs().values())))
        time.sleep(0.3)
        self.assertFalse(waiting.exists(), "앞선 재생이 끝나기 전에는 시작하지 않는다")
        # 대기 중인 작업도 pause로 끝나고, 잠금을 쥔 다른 에이전트의 작업은 그대로다.
        self.assertEqual(playback.pause(self.agent), 1)
        self.assertTrue(wait_until(lambda: self.jobs() == {}))
        self.assertEqual(len(self.jobs(other)), 1)
        # 잠금을 쥔 작업자가 정리 없이 죽어도 다음 작업이 진행된다.
        playback.start(self.sleeping_command(next_job), self.agent, background=True, stdin=subprocess.DEVNULL, queue=True)
        time.sleep(0.3)
        self.assertFalse(next_job.exists())
        (pid,) = [job["pid"] for job in self.jobs(other).values()]
        os.killpg(pid, signal.SIGKILL)
        self.assertTrue(wait_until(next_job.exists))
        self.assertFalse(waiting.exists())

    def test_queue_wait_expires_and_unusable_lock_still_runs(self):
        other = self.other_agent()
        holder, late, blocked = self.home / "holder", self.home / "late", self.home / "blocked"
        playback.start(self.sleeping_command(holder), other, background=True, stdin=subprocess.DEVNULL, queue=True)
        self.assertTrue(wait_until(holder.exists))
        # 차례가 제한 시간 안에 오지 않으면 기다림을 그만두고 재생한다.
        with patch.dict(os.environ, {"TTS_PLAYBACK_QUEUE_WAIT": "1"}):
            playback.start(self.sleeping_command(late), self.agent, background=True, stdin=subprocess.DEVNULL, queue=True)
            time.sleep(0.4)
            self.assertFalse(late.exists())
            self.assertTrue(wait_until(late.exists, seconds=5))
        # 잠금 파일을 만들 수 없어도 재생은 한다.
        (self.home / "not-a-directory").write_text("")
        with patch.dict(os.environ, {"TTS_PLAYBACK_LOCK": str(self.home / "not-a-directory/playback.lock")}):
            playback.start(self.sleeping_command(blocked), self.agent, background=True, stdin=subprocess.DEVNULL, queue=True)
            self.assertTrue(wait_until(blocked.exists))

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
        # 세션 식별자를 받으면 공백 억제 파일을 그 세션의 요약 파일에 쓰고 공용 파일은 그대로 둔다.
        summary.write_text("다른 세션 요약")
        subprocess.run(["bash", str(hooks / "tts-pause.sh"), "session-a"], env=env, capture_output=True, check=True)
        self.assertEqual((self.agent / "TTS-Summary/pending/session-a.txt").read_text(), "\n")
        self.assertEqual(summary.read_text(), "다른 세션 요약")

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
        # launchd 작업자도 훅이 넘긴 환경의 잠금 파일로 재생 큐에 선다.
        self.assertTrue(self.lock.exists())
        self.assertEqual(playback.pause(self.agent), 1)
        time.sleep(.1)
        self.assertFalse(finished.exists())
        self.assertEqual(self.jobs(), {})
        self.assertFalse((self.agent / "tts-summary.txt").exists())

    @unittest.skipUnless(sys.platform == "darwin", "macOS launchd integration")
    def test_two_sessions_stop_hooks_play_both_summaries_in_turn(self):
        hooks = self.agent / "hooks"
        hooks.mkdir()
        for name in ("stop-tts.sh", "tts-config.sh", "tts_playback.py"):
            shutil.copy2(ROOT / "assets/macos" / name, hooks / name)
        pending = self.agent / "TTS-Summary/pending"
        pending.mkdir(parents=True)
        (self.agent / "TTS-Summary/tts-config.txt").write_text("enabled=on\nprovider=gemini-api\n")
        log = self.home / "spoken.log"
        # 유료 호출·소리 없이 재생 구간만 기록하는 가짜 provider.
        (hooks / "play-tts-gemini-api.sh").write_text(
            '#!/bin/bash\nprintf "start %s\\n" "$1" >> "$TTS_TEST_LOG"\nsleep 0.5\n'
            'printf "end %s\\n" "$1" >> "$TTS_TEST_LOG"\nexit 0\n')
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=".claude", TTS_SUMMARY="on", TTS_TEST_LOG=str(log))
        for session in ("first", "second"):
            (pending / f"{session}.txt").write_text(f"{session}-요약")
        for session in ("first", "second"):
            before = time.monotonic()
            result = subprocess.run(["bash", str(hooks / "stop-tts.sh")], input=json.dumps({"session_id": session}),
                                    env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLess(time.monotonic() - before, 3, "훅은 앞선 재생을 기다리지 않는다")
            self.assertTrue(wait_until(log.exists))
        self.assertTrue(wait_until(lambda: log.read_text().count("end ") == 2, seconds=10))
        self.assertEqual(log.read_text().splitlines(),
                         ["start first-요약", "end first-요약", "start second-요약", "end second-요약"])
        self.assertEqual(list(pending.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
