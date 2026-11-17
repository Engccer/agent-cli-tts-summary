#!/usr/bin/env python3
"""세션별 다시 듣기 계약(macOS): Stop 작업자(stop-tts.sh --speak)가 세션마다 마지막 요약 음성을 기록하고,
tts-replay.sh가 그 세션의 음성만 고른다. say·afconvert·afplay·provider는 가짜라 소리와 네트워크가 없다.
실행: python scripts/test_session_replay.py
"""

from __future__ import annotations
import sys
import unittest

if sys.platform != "darwin":
    raise unittest.SkipTest("macOS 전용 스크립트를 실행하는 테스트다")

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import time


MACOS = Path(__file__).resolve().parents[1] / "assets" / "macos"

FAKE_PROVIDER = """#!/usr/bin/env bash
OUT="$HOME/$AGENT_DIR_NAME/TTS-Summary/wav/tts-fake-$$.wav"
mkdir -p "${OUT%/*}"
[ ! -f "$HOME/provider-fails" ] || exit 1
printf 'RIFF%s' "$1" > "$OUT"
echo "[OK] Saved to: $OUT"
afplay "$OUT"
"""
FAKE_PRESYNTH = """#!/usr/bin/env bash
[ "$1" = "--take" ] && [ -f "$HOME/presynth.wav" ] && printf '%s' "$HOME/presynth.wav"
"""
FAKE_SAY = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do
  [ "$1" != "-o" ] || { printf 'FORM' > "$2"; exit 0; }
  shift
done
"""
FAKE_AFCONVERT = """#!/usr/bin/env bash
cp "$1" "$2"
"""
FAKE_AFPLAY = """#!/usr/bin/env bash
sleep "${FAKE_AFPLAY_SECONDS:-0}"
"""


class SessionReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="tts-session-replay-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.agent = self.home / ".claude"
        self.hooks = self.agent / "hooks"
        self.hooks.mkdir(parents=True)
        for name in ("stop-tts.sh", "tts-replay.sh", "tts-config.sh", "tts_playback.py"):
            shutil.copy(MACOS / name, self.hooks / name)
        (self.hooks / "play-tts-azure-api.sh").write_text(FAKE_PROVIDER)
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        for name, body in (("say", FAKE_SAY), ("afconvert", FAKE_AFCONVERT), ("afplay", FAKE_AFPLAY)):
            (bin_dir / name).write_text(body)
            (bin_dir / name).chmod(0o755)
        self.wav = self.agent / "TTS-Summary" / "wav"
        self.records = self.agent / "TTS-Summary" / "replay"
        self.config("azure-api")

    def config(self, provider: str) -> None:
        path = self.agent / "TTS-Summary" / "tts-config.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"provider={provider}\n", encoding="utf-8")

    def env(self, **extra: str) -> dict[str, str]:
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=".claude", TTS_SUMMARY="on",
                   PATH=f"{self.home / 'bin'}:{os.environ['PATH']}")
        for name in ("CLAUDE_CONFIG_DIR", "CLAUDE_SESSION_ID", "TTS_SESSION_ID"):
            env.pop(name, None)
        env.update(extra)
        return env

    def speak(self, text: str, sid: str | None, *args: str) -> None:
        extra = {"TTS_SESSION_ID": sid} if sid is not None else {}
        completed = subprocess.run(["/bin/bash", str(self.hooks / "stop-tts.sh"), "--speak", *args], input=text,
                                   env=self.env(**extra), capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        time.sleep(0.05)  # 보관 파일의 수정 시각 순서를 분명히 한다.

    def replay(self, *args: str) -> str:
        completed = subprocess.run(["/bin/bash", str(self.hooks / "tts-replay.sh"), *args],
                                   env=self.env(TTS_REPLAY_DRYRUN="1"), capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout

    def recorded(self, sid: str) -> Path:
        return self.wav / (self.records / f"{sid}.txt").read_text().strip()

    def test_each_session_replays_its_own_last_audio(self) -> None:
        self.speak("가 세션 첫 요약", "sess-a")
        self.speak("가 세션 둘째 요약", "sess-a")
        self.speak("나 세션 요약", "sess-b")
        own_a, own_b = self.recorded("sess-a"), self.recorded("sess-b")
        self.assertEqual(own_a.read_text(), "RIFF가 세션 둘째 요약")
        self.assertEqual(own_b.read_text(), "RIFF나 세션 요약")
        out = self.replay("sess-a")
        self.assertIn(f"file={own_a}", out)
        self.assertIn("이 세션의 직전 요약 음성", out)
        self.assertIn(f"file={own_b}", self.replay("sess-b"))
        # 세션을 모르면 보관함에서 가장 최근 파일을 튼다.
        self.assertIn(f"file={own_b}", self.replay())
        self.assertEqual(sorted(p.name for p in self.records.iterdir()), ["sess-a.txt", "sess-b.txt"])

    def test_builtin_voice_path_is_recorded(self) -> None:
        self.config("say")
        self.speak("내장 음성 요약", "sess-a")
        self.assertEqual(self.recorded("sess-a").suffix, ".wav")
        self.assertIn(f"file={self.recorded('sess-a')}", self.replay("sess-a"))

    def test_interim_and_unknown_session_leave_no_record(self) -> None:
        self.speak("가 세션 요약", "sess-a")
        own = self.recorded("sess-a")
        self.speak("중간 보고", "sess-a", "--interim")
        self.speak("세션 모르는 요약", None)
        self.speak("잘못된 식별자", "../evil")
        self.assertEqual(self.recorded("sess-a"), own)
        self.assertEqual([p.name for p in self.records.iterdir()], ["sess-a.txt"])

    def test_session_without_audio_does_not_play_another_sessions(self) -> None:
        self.speak("나 세션 요약", "sess-b")
        out = self.replay("sess-a")
        self.assertNotIn("file=", out)
        self.assertIn("이 세션에서 만든 요약 음성이 보관함에 없습니다", out)
        # 기록이 가리키는 파일이 보관함에서 밀려났거나 기록이 보관함 밖을 가리켜도 틀지 않는다.
        self.recorded("sess-b").unlink()
        self.assertNotIn("file=", self.replay("sess-b"))
        (self.records / "sess-b.txt").write_text("../../tts-config.txt\n")
        self.assertNotIn("file=", self.replay("sess-b"))

    def test_provider_failure_records_builtin_voice_fallback(self) -> None:
        (self.home / "provider-fails").write_text("")
        self.speak("폴백 요약", "sess-a")
        self.assertRegex(self.recorded("sess-a").name, r"^tts-\d{8}-\d{6}\.wav$")

    def test_presynthesized_audio_is_recorded(self) -> None:
        (self.hooks / "tts-presynth.sh").write_text(FAKE_PRESYNTH)
        (self.home / "presynth.wav").write_text("RIFF미리 합성본")
        self.speak("미리 합성된 요약", "sess-a")
        self.assertEqual(self.recorded("sess-a").read_text(), "RIFF미리 합성본")
        self.assertIn(f"file={self.recorded('sess-a')}", self.replay("sess-a"))

    def test_record_survives_pause_during_playback(self) -> None:
        """실제 구조(재생 관리자 작업자 아래의 Stop 작업자)에서 재생 도중 pause해도 기록이 남는다."""
        playback = ["python3", str(self.hooks / "tts_playback.py")]
        env = self.env(TTS_SESSION_ID="sess-a", FAKE_AFPLAY_SECONDS="30",
                       TTS_PLAYBACK_LOCK=str(self.home / "playback.lock"))
        process = subprocess.Popen([*playback, "run", "--queue", "--agent-dir", str(self.agent), "--",
                                    "/bin/bash", str(self.hooks / "stop-tts.sh"), "--speak"],
                                   stdin=subprocess.PIPE, env=env, text=True)
        process.stdin.write("재생 도중 중지되는 요약")
        process.stdin.close()
        deadline = time.time() + 10
        # 기록은 재생이 끝나기 전에(가짜 afplay가 30초 자는 동안) 이미 남아 있어야 한다.
        while time.time() < deadline and not (self.records / "sess-a.txt").exists():
            time.sleep(0.02)
        paused = subprocess.run([*playback, "pause", "--agent-dir", str(self.agent)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertIn("중지했습니다", paused.stdout)
        process.wait(timeout=10)
        self.assertEqual(self.recorded("sess-a").read_text(), "RIFF재생 도중 중지되는 요약")


if __name__ == "__main__":
    unittest.main()
