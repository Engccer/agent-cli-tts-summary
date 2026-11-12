#!/usr/bin/env python3
"""macOS Stop hook의 요약 누락 가드, 세션 음소거(TTS_SUMMARY=off), 세션별 요약 파일 계약을 검증한다.
재생 경로(say)까지 가지 않는 분기만 다루고, 재생 전달은 가짜 tts_playback.py로 받아 소리가 나지 않는다.
실행: python scripts/test_stop_tts_mute.py
"""

from __future__ import annotations
import sys
import unittest

if sys.platform != "darwin":
    raise unittest.SkipTest("macOS 전용 스크립트를 실행하는 테스트다")


import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
STOP_HOOK = ROOT / "assets" / "macos" / "stop-tts.sh"
AGENT_DIR_NAME = ".codex"  # 자산 템플릿의 기본값


class StopTtsMuteTests(unittest.TestCase):
    def run_hook(self, *, summary: str | None, session_env: dict[str, str], config: str = "enabled=on\n",
                 payload: str = "{}", agent_name: str = AGENT_DIR_NAME) -> tuple[subprocess.CompletedProcess, Path]:
        tmp = tempfile.mkdtemp()
        home = Path(tmp)
        agent_dir = home / agent_name
        (agent_dir / "TTS-Summary").mkdir(parents=True)
        (agent_dir / "TTS-Summary" / "tts-config.txt").write_text(config, encoding="utf-8")
        summary_file = agent_dir / "tts-summary.txt"
        if summary is not None:
            summary_file.write_text(summary, encoding="utf-8")
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["AGENT_DIR_NAME"] = agent_name
        env.pop("TTS_SUMMARY", None)
        env.update(session_env)
        completed = subprocess.run(
            ["bash", str(STOP_HOOK)], input=payload, capture_output=True, text=True, env=env,
        )
        return completed, summary_file

    def test_missing_summary_blocks_once_in_normal_session(self) -> None:
        """단독 세션 회귀: 요약이 없으면 exit 2로 한 번 되돌린다."""
        completed, _ = self.run_hook(summary=None, session_env={}, agent_name=".claude")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("TTS 요약 누락", completed.stderr)

    def test_missing_summary_passes_after_retry(self) -> None:
        completed, _ = self.run_hook(summary=None, session_env={}, payload='{"stop_hook_active": true}', agent_name=".claude")
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

    def test_agy_missing_summary_emits_continue_decision_on_first_stop(self) -> None:
        import json
        completed, _ = self.run_hook(
            summary=None,
            session_env={},
            payload='{"executionNum": 1, "terminationReason": "NO_TOOL_CALL", "fullyIdle": true}',
            agent_name=".gemini",
        )
        self.assertEqual(completed.returncode, 0)
        decision = json.loads(completed.stdout)
        self.assertEqual(decision["decision"], "continue")
        self.assertIn("TTS 요약 누락", decision["reason"])

    def test_agy_missing_summary_passes_on_retry_or_non_normal_stop(self) -> None:
        import json
        for payload in (
            '{"executionNum": 2, "terminationReason": "NO_TOOL_CALL", "fullyIdle": true}',
            '{"executionNum": 1, "terminationReason": "ERROR", "fullyIdle": true}',
            '{"executionNum": 1, "terminationReason": "NO_TOOL_CALL", "fullyIdle": false}',
        ):
            with self.subTest(payload=payload):
                completed, _ = self.run_hook(summary=None, session_env={}, payload=payload, agent_name=".gemini")
                self.assertEqual(completed.returncode, 0)
                self.assertEqual(json.loads(completed.stdout), {})


class StopTtsSessionFileTests(unittest.TestCase):
    """세션 전용 요약 파일(TTS-Summary/pending/<sid>.txt) 우선, 공용 파일 폴백, 남의 파일 불간섭."""

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="tts-stop-session-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.calls = self.home / "calls.jsonl"

    def agent(self, name: str) -> Path:
        agent = self.home / name
        hooks = agent / "hooks"
        if not hooks.exists():
            hooks.mkdir(parents=True)
            for script in ("stop-tts.sh", "tts-config.sh"):
                shutil.copy(ROOT / "assets" / "macos" / script, hooks / script)
            # 재생 작업 등록을 가로채 인자와 본문만 기록한다(launchd·소리 없음).
            (hooks / "tts_playback.py").write_text(
                "import json, os, sys\n"
                "with open(os.environ['CALLS'], 'a') as stream:\n"
                "    stream.write(json.dumps({'args': sys.argv[1:], 'text': sys.stdin.read()}) + '\\n')\n")
            (agent / "TTS-Summary" / "pending").mkdir(parents=True)
            self.config(name, "enabled=on\n")
        return agent

    def config(self, name: str, text: str) -> None:
        (self.home / name / "TTS-Summary" / "tts-config.txt").write_text(text, encoding="utf-8")

    def session_file(self, name: str, sid: str) -> Path:
        return self.agent(name) / "TTS-Summary" / "pending" / f"{sid}.txt"

    def run_stop(self, name: str, payload: dict, **session_env: str) -> subprocess.CompletedProcess:
        agent = self.agent(name)
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=name, CALLS=str(self.calls))
        for key in ("TTS_SUMMARY", "CLAUDE_CONFIG_DIR", "ANTIGRAVITY_CONVERSATION_ID"):
            env.pop(key, None)
        env.update(session_env)
        return subprocess.run(["bash", str(agent / "hooks" / "stop-tts.sh")], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)

    def dispatched(self) -> list[dict]:
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_session_file_wins_and_shared_file_is_left_alone(self) -> None:
        own, other = self.session_file(".claude", "mine"), self.session_file(".claude", "other")
        shared = self.agent(".claude") / "tts-summary.txt"
        own.write_text("내 세션 요약", encoding="utf-8")
        other.write_text("다른 세션 요약", encoding="utf-8")
        shared.write_text("공용 파일 요약", encoding="utf-8")
        completed = self.run_stop(".claude", {"session_id": "mine", "stop_hook_active": False})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = self.dispatched()
        self.assertEqual([call["text"] for call in calls], ["내 세션 요약"])
        self.assertIn("--queue", calls[0]["args"])
        self.assertIn("--launchd", calls[0]["args"])
        self.assertFalse(own.exists())
        self.assertEqual(other.read_text(encoding="utf-8"), "다른 세션 요약")
        self.assertEqual(shared.read_text(encoding="utf-8"), "공용 파일 요약")

    def test_shared_file_is_fallback_when_session_file_is_missing(self) -> None:
        shared = self.agent(".claude") / "tts-summary.txt"
        other = self.session_file(".claude", "other")
        other.write_text("다른 세션 요약", encoding="utf-8")
        shared.write_text("공용 파일 요약", encoding="utf-8")
        completed = self.run_stop(".claude", {"session_id": "mine"})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call["text"] for call in self.dispatched()], ["공용 파일 요약"])
        self.assertFalse(shared.exists())
        self.assertEqual(other.read_text(encoding="utf-8"), "다른 세션 요약")

    def test_blank_file_suppresses_playback_on_both_paths(self) -> None:
        own = self.session_file(".claude", "mine")
        shared = self.agent(".claude") / "tts-summary.txt"
        own.write_text("\n", encoding="utf-8")
        shared.write_text("공용 파일 요약", encoding="utf-8")
        completed = self.run_stop(".claude", {"session_id": "mine"})
        self.assertEqual((completed.returncode, completed.stderr), (0, ""))
        self.assertFalse(own.exists())
        self.assertEqual(shared.read_text(encoding="utf-8"), "공용 파일 요약")
        # 스크립트가 세션을 몰라 공용 파일에 써 둔 공백 억제도 그대로 통한다.
        shared.write_text("\n", encoding="utf-8")
        completed = self.run_stop(".claude", {"session_id": "mine"})
        self.assertEqual((completed.returncode, completed.stderr), (0, ""))
        self.assertFalse(shared.exists())
        self.assertEqual(self.dispatched(), [])

    def test_missing_guard_names_session_file_or_shared_file(self) -> None:
        agent = self.agent(".claude")
        completed = self.run_stop(".claude", {"session_id": "mine", "stop_hook_active": False})
        self.assertEqual(completed.returncode, 2)
        self.assertIn(f"요약을 {agent}/TTS-Summary/pending/mine.txt 에 파일 편집 도구로", completed.stderr)
        for payload in ({}, {"session_id": "../evil"}, {"session_id": "a/b"}):
            with self.subTest(payload=payload):
                completed = self.run_stop(".claude", payload)
                self.assertEqual(completed.returncode, 2)
                self.assertIn(f"요약을 {agent}/tts-summary.txt 에 파일 편집 도구로", completed.stderr)
        self.assertEqual(self.run_stop(".claude", {"session_id": "mine", "stop_hook_active": True}).returncode, 0)
        self.assertEqual(sorted(p.name for p in agent.parent.iterdir() if p.name == "evil"), [])

    def test_agy_uses_conversation_id_for_session_file_and_guard(self) -> None:
        agent = self.agent(".gemini")
        stop = {"executionNum": 1, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True}
        decision = json.loads(self.run_stop(".gemini", dict(stop, conversationId="conv-1")).stdout)
        self.assertEqual(decision["decision"], "continue")
        self.assertIn(f"{agent}/TTS-Summary/pending/conv-1.txt 에", decision["reason"])
        # payload에 없으면 환경 변수의 대화 식별자를 쓴다.
        decision = json.loads(self.run_stop(".gemini", stop, ANTIGRAVITY_CONVERSATION_ID="conv-2").stdout)
        self.assertIn(f"{agent}/TTS-Summary/pending/conv-2.txt 에", decision["reason"])
        decision = json.loads(self.run_stop(".gemini", stop).stdout)
        self.assertIn(f"{agent}/tts-summary.txt 에", decision["reason"])

        own = self.session_file(".gemini", "conv-1")
        own.write_text("agy 세션 요약", encoding="utf-8")
        (agent / "tts-summary.txt").write_text("공용 파일 요약", encoding="utf-8")
        completed = self.run_stop(".gemini", dict(stop, conversationId="conv-1"))
        self.assertEqual(json.loads(completed.stdout), {})
        self.assertEqual([call["text"] for call in self.dispatched()], ["agy 세션 요약"])
        self.assertTrue((agent / "tts-summary.txt").exists())

    def test_disabled_clears_own_and_shared_files_but_muted_touches_nothing(self) -> None:
        own, other = self.session_file(".claude", "mine"), self.session_file(".claude", "other")
        shared = self.agent(".claude") / "tts-summary.txt"
        for path in (own, other, shared):
            path.write_text("남은 요약", encoding="utf-8")
        completed = self.run_stop(".claude", {"session_id": "mine"}, TTS_SUMMARY="off")
        self.assertEqual((completed.returncode, completed.stderr), (0, ""))
        self.assertTrue(own.exists() and other.exists() and shared.exists())
        self.config(".claude", "enabled=off\n")
        completed = self.run_stop(".claude", {"session_id": "mine"})
        self.assertEqual((completed.returncode, completed.stderr), (0, ""))
        self.assertFalse(own.exists() or shared.exists())
        self.assertTrue(other.exists())
        self.assertEqual(self.dispatched(), [])

    def test_stop_removes_session_files_older_than_a_day(self) -> None:
        stale, fresh = self.session_file(".claude", "stale"), self.session_file(".claude", "fresh")
        own = self.session_file(".claude", "mine")
        nested = stale.parent / "turn-x" / "tts-summary.txt"  # 다른 소비자의 하위 폴더는 대상이 아니다.
        nested.parent.mkdir()
        for path in (stale, fresh, nested):
            path.write_text("Stop까지 못 간 요약", encoding="utf-8")
        own.write_text("\n", encoding="utf-8")
        old = __import__("time").time() - 25 * 3600
        for path in (stale, nested):
            os.utime(path, (old, old))
        recent = __import__("time").time() - 23 * 3600
        os.utime(fresh, (recent, recent))
        self.assertEqual(self.run_stop(".claude", {"session_id": "mine"}).returncode, 0)
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists() and nested.exists())
        # 세션 음소거는 정리도 하지 않는다.
        stale.write_text("남의 것일 수 있음", encoding="utf-8")
        os.utime(stale, (old, old))
        self.run_stop(".claude", {"session_id": "mine"}, TTS_SUMMARY="off")
        self.assertTrue(stale.exists())


if __name__ == "__main__":
    unittest.main()
