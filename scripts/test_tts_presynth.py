#!/usr/bin/env python3
"""요약 음성 미리 합성(tts-presynth.sh)과 Stop 훅의 캐시 재생 계약을 무음으로 검증한다."""

from __future__ import annotations
import sys
import unittest

if sys.platform != "darwin":
    raise unittest.SkipTest("macOS 전용 스크립트를 실행하는 테스트다")

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
MACOS = ROOT / "assets" / "macos"
TEXT = "작업을 마쳤습니다. 테스트가 통과했습니다."

FAKE_PROVIDER = """#!/usr/bin/env bash
# 가짜 azure provider: 호출 횟수를 남기고 WAV 자리만 만든다.
AGENT_DIR="$HOME/.claude"
echo "$1" >> "$AGENT_DIR/provider-calls"
mkdir -p "$AGENT_DIR/TTS-Summary/wav"
OUT="$AGENT_DIR/TTS-Summary/wav/tts-fake-$$.wav"
printf 'RIFFfake' > "$OUT"
echo "[OK] Saved to: $OUT"
[ -n "$TTS_NO_PLAY" ] || afplay "$OUT"
exit 0
"""

FAKE_AFPLAY = """#!/usr/bin/env bash
echo "$1" >> "$HOME/.claude/afplay-calls"
"""


def sandboxed(command: list[str]) -> list[str]:
    """회귀가 생겨도 실제 음성·launchd·네트워크에 닿지 않게 한다."""
    if shutil.which("sandbox-exec"):
        policy = ('(version 1)(allow default)(deny network*)'
                  '(deny process-exec (literal "/usr/bin/say")'
                  '(literal "/usr/bin/afplay")(literal "/bin/launchctl"))')
        return ["sandbox-exec", "-p", policy, *command]
    return command


class PresynthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="tts-presynth-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.agent = self.home / ".claude"
        self.hooks = self.agent / "hooks"
        self.hooks.mkdir(parents=True)
        for name in ("stop-tts.sh", "tts-presynth.sh", "tts-config.sh", "tts_playback.py"):
            shutil.copy(MACOS / name, self.hooks / name)
        (self.hooks / "play-tts-azure-api.sh").write_text(FAKE_PROVIDER)
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        (bin_dir / "afplay").write_text(FAKE_AFPLAY)
        (bin_dir / "afplay").chmod(0o755)
        self.path = f"{bin_dir}:{os.environ['PATH']}"
        self.summary = self.agent / "tts-summary.txt"
        self.cache = self.agent / "TTS-Summary" / "presynth"
        self.write_config(provider="azure-api", voice_azure="ko-KR-HyunsuNeural", speed="7.5")

    def write_config(self, **values: str) -> None:
        config = self.agent / "TTS-Summary" / "tts-config.txt"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")

    def env(self) -> dict[str, str]:
        env = dict(os.environ, HOME=str(self.home), PATH=self.path, AGENT_DIR_NAME=".claude",
                   TTS_SUMMARY="on", TTS_PRESYNTH_INLINE="1")
        env.pop("CLAUDE_CONFIG_DIR", None)
        return env

    def run_hook(self, name: str, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
        completed = subprocess.run(sandboxed(["bash", str(self.hooks / name), *args]), input=stdin,
                                   env=self.env(), capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed

    def post_write(self, path: Path, text: str = TEXT) -> None:
        path.write_text(text, encoding="utf-8")
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": text}}
        self.run_hook("tts-presynth.sh", stdin=json.dumps(payload, ensure_ascii=False))

    def lines(self, name: str) -> list[str]:
        path = self.agent / name
        return path.read_text().splitlines() if path.exists() else []

    def test_summary_write_presynthesizes_and_stop_plays_cache(self) -> None:
        self.post_write(self.summary)
        self.assertEqual(len(self.lines("provider-calls")), 1)
        self.assertEqual(len(list(self.cache.glob("*.wav"))), 1)
        self.assertEqual(self.lines("afplay-calls"), [], "미리 합성 단계는 재생하지 않는다")

        self.run_hook("stop-tts.sh", "--speak", stdin=TEXT)
        self.assertEqual(len(self.lines("provider-calls")), 1, "캐시가 있으면 다시 합성하지 않는다")
        played = self.lines("afplay-calls")
        self.assertEqual(len(played), 1)
        self.assertTrue(played[0].startswith(str(self.agent / "TTS-Summary" / "wav" / "tts-")))
        self.assertTrue(Path(played[0]).exists(), "재생본은 보관 폴더에 남아 /tts-replay가 쓴다")
        self.assertEqual(list(self.cache.glob("*.wav")), [])

    def test_session_summary_write_presynthesizes_that_file(self) -> None:
        """훅 입력에 세션 요약 파일 경로가 있으면 공용 파일이 아니라 그 파일을 읽어 합성한다."""
        self.summary.write_text("다른 세션이 방금 쓴 요약입니다.", encoding="utf-8")
        own = self.agent / "TTS-Summary" / "pending" / "sess_1-A.txt"
        own.parent.mkdir(parents=True)
        self.post_write(own)
        self.assertEqual(self.lines("provider-calls"), [TEXT])
        self.assertEqual(self.lines("afplay-calls"), [])
        self.run_hook("stop-tts.sh", "--speak", stdin=TEXT)
        self.assertEqual(len(self.lines("provider-calls")), 1, "세션 파일에서 합성한 음성을 Stop이 꺼내 쓴다")
        self.assertEqual(len(self.lines("afplay-calls")), 1)

    def test_other_agents_or_stale_session_summary_is_ignored(self) -> None:
        other = self.home / ".codex" / "TTS-Summary" / "pending" / "sess-1.txt"
        other.parent.mkdir(parents=True)
        self.post_write(other)  # 다른 에이전트의 세션 파일
        own = self.agent / "TTS-Summary" / "pending" / "sess-1.txt"
        own.parent.mkdir(parents=True)
        own.write_text(TEXT, encoding="utf-8")
        old = time.time() - 600
        os.utime(own, (old, old))
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(self.home / "doc.md"),
                   "content": f"요약 경로는 {own} 이다"}}
        self.run_hook("tts-presynth.sh", stdin=json.dumps(payload, ensure_ascii=False))
        self.assertEqual(self.lines("provider-calls"), [])

    def test_other_files_and_say_provider_are_ignored(self) -> None:
        self.post_write(self.home / "notes.txt")
        self.write_config(provider="say")
        self.post_write(self.summary)
        self.assertEqual(self.lines("provider-calls"), [])
        self.assertFalse(self.cache.exists() and any(self.cache.iterdir()))

    def test_changed_text_or_voice_misses_cache(self) -> None:
        self.post_write(self.summary)
        self.write_config(provider="azure-api", voice_azure="ko-KR-SunHiNeural", speed="7.5")
        self.run_hook("stop-tts.sh", "--speak", stdin=TEXT)
        self.run_hook("stop-tts.sh", "--speak", stdin=TEXT + " 덧붙임")
        self.assertEqual(len(self.lines("provider-calls")), 3)

    def test_dead_worker_does_not_block_stop(self) -> None:
        self.post_write(self.summary)
        wav = next(self.cache.glob("*.wav"))
        wav.unlink()
        dead = subprocess.Popen(["true"])
        dead.wait()
        wav.with_suffix(".pending").write_text(str(dead.pid))
        started = time.monotonic()
        self.run_hook("stop-tts.sh", "--speak", stdin=TEXT)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(len(self.lines("provider-calls")), 2, "죽은 작업자면 평소대로 합성한다")

    def test_take_waits_for_running_worker(self) -> None:
        self.post_write(self.summary)
        wav = next(self.cache.glob("*.wav"))
        hidden = wav.with_suffix(".hold")
        wav.rename(hidden)
        worker = subprocess.Popen(["sleep", "5"])
        self.addCleanup(worker.wait)
        self.addCleanup(worker.kill)
        wav.with_suffix(".pending").write_text(str(worker.pid))
        finisher = subprocess.Popen(["bash", "-c", f"sleep 0.6; mv '{hidden}' '{wav}'; rm -f '{wav.with_suffix('.pending')}'"])
        self.run_hook("stop-tts.sh", "--speak", stdin=TEXT)
        finisher.wait()
        self.assertEqual(len(self.lines("provider-calls")), 1, "합성 중이면 끝나기를 기다려 그 음성을 쓴다")
        self.assertEqual(len(self.lines("afplay-calls")), 1)

    def test_codex_apply_patch_payload_presynthesizes(self) -> None:
        codex = self.home / ".codex"
        hooks = codex / "hooks-macos"
        hooks.mkdir(parents=True)
        for name in ("tts-presynth.sh", "tts-config.sh"):
            shutil.copy(MACOS / name, hooks / name)
        (hooks / "play-tts-azure-api.sh").write_text(FAKE_PROVIDER.replace('AGENT_DIR="$HOME/.claude"', 'AGENT_DIR="$HOME/.codex"'))
        config = codex / "TTS-Summary" / "tts-config.txt"
        config.parent.mkdir(parents=True)
        config.write_text("provider=azure-api\n", encoding="utf-8")
        (codex / "tts-summary.txt").write_text(TEXT + "\r\n", encoding="utf-8")
        env = dict(self.env(), AGENT_DIR_NAME=".codex")

        def hook(path: Path) -> None:
            patch = f"*** Begin Patch\n*** Add File: {path}\n+{TEXT}\n*** End Patch"
            payload = {"hook_event_name": "PostToolUse", "tool_name": "apply_patch",
                       "tool_input": {"command": patch}}
            subprocess.run(sandboxed(["bash", str(hooks / "tts-presynth.sh")]), env=env, check=True,
                           input=json.dumps(payload, ensure_ascii=False), text=True, timeout=30)

        hook(self.summary)  # 다른 에이전트(.claude)의 요약 파일은 무시한다.
        self.assertFalse((codex / "provider-calls").exists())
        hook(codex / "tts-summary.txt")
        self.assertEqual(len((codex / "provider-calls").read_text().splitlines()), 1)
        # Codex Stop은 Python read_text로 CRLF를 LF로 바꿔 넘긴다. 키가 같아야 한다.
        taken = subprocess.run(sandboxed(["bash", str(hooks / "tts-presynth.sh"), "--take"]), env=env,
                               input=TEXT, capture_output=True, text=True, timeout=30).stdout
        self.assertTrue(taken.startswith(str(codex / "TTS-Summary" / "presynth")), taken)

    def test_agy_write_file_payload_presynthesizes_and_prints_json(self) -> None:
        agy = self.home / ".gemini"
        hooks = agy / "hooks"
        hooks.mkdir(parents=True)
        for name in ("tts-presynth.sh", "tts-config.sh"):
            shutil.copy(MACOS / name, hooks / name)
        (hooks / "play-tts-azure-api.sh").write_text(FAKE_PROVIDER.replace('AGENT_DIR="$HOME/.claude"', 'AGENT_DIR="$HOME/.gemini"'))
        config = agy / "TTS-Summary" / "tts-config.txt"
        config.parent.mkdir(parents=True)
        config.write_text("provider=azure-api\n", encoding="utf-8")
        summary = agy / "tts-summary.txt"
        summary.write_text(TEXT, encoding="utf-8")
        env = dict(self.env(), AGENT_DIR_NAME=".gemini")

        def hook(path: Path) -> str:
            payload = {"hookEventName": "PostToolUse", "error": "",
                       "toolCall": {"name": "write_file", "args": {"Path": str(path), "Content": TEXT}}}
            return subprocess.run(sandboxed(["bash", str(hooks / "tts-presynth.sh")]), env=env, check=True,
                                  input=json.dumps(payload), capture_output=True, text=True, timeout=30).stdout

        self.assertEqual(hook(self.home / "notes.txt").strip(), "{}")
        self.assertFalse((agy / "provider-calls").exists())
        self.assertEqual(hook(summary).strip(), "{}")
        self.assertEqual(len((agy / "provider-calls").read_text().splitlines()), 1)
        # 조기 종료 경로도 {}를 낸다.
        config.write_text("enabled=off\nprovider=azure-api\n", encoding="utf-8")
        self.assertEqual(hook(summary).strip(), "{}")

    def test_stale_summary_is_not_presynthesized(self) -> None:
        self.summary.write_text(TEXT, encoding="utf-8")
        old = time.time() - 600
        os.utime(self.summary, (old, old))
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(self.home / "doc.md"),
                   "content": f"요약 경로는 {self.summary} 이다"}}
        self.run_hook("tts-presynth.sh", stdin=json.dumps(payload, ensure_ascii=False))
        self.assertEqual(self.lines("provider-calls"), [])


if __name__ == "__main__":
    unittest.main()
