#!/usr/bin/env python3
"""Windows 훅의 동시 세션 계약을 검증한다: 세션 전용 요약 파일(TTS-Summary\\pending\\<세션>.txt)과 재생 대기열.
provider는 시각만 기록하는 가짜로 바꾸고 대기열 이름도 시험마다 따로 써서 소리가 나지 않고 실제 재생과 얽히지 않는다.
PowerShell이 있는 환경(Windows)에서만 돌고, 없으면 건너뛴다.
실행: python scripts/test_concurrent_sessions_windows.py
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "assets" / "windows"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
SESSION_A = "11111111-aaaa-4aaa-8aaa-111111111111"
SESSION_B = "22222222-bbbb-4bbb-8bbb-222222222222"

# 재생 대신 시작·끝 시각과 받은 글을 기록하는 가짜 provider. 재생 시간은 잠깐의 대기로 흉내 낸다.
FAKE_PROVIDER = r"""
param([string]$Text, [string]$VoiceOverride)
$record = Join-Path $env:FAKE_TTS_DIR ("call-" + $PID + ".txt")
$start = [DateTime]::UtcNow.Ticks
Start-Sleep -Milliseconds 1500
$end = [DateTime]::UtcNow.Ticks
[System.IO.File]::WriteAllLines($record, [string[]]@("$start", "$end", $Text), (New-Object System.Text.UTF8Encoding $false))
Write-Host "[OK] Saved to: $env:FAKE_TTS_DIR\tts-fake-$PID.wav"
exit 0
"""


@unittest.skipUnless(POWERSHELL, "PowerShell이 없는 환경")
class WindowsConcurrentSessionTests(unittest.TestCase):
    def make_home(self, agent_dir_name: str = ".claude", config: str = "enabled=on\n") -> None:
        self.home = Path(tempfile.mkdtemp(prefix="tts-concurrent-win-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.hooks = self.home / "hooks"
        self.hooks.mkdir()
        for source in WINDOWS.glob("*.ps1"):
            text = source.read_text(encoding="utf-8-sig")
            for default in ('".codex"', '".claude"', '".gemini"'):
                text = text.replace(f"$AgentDirName = {default}", f'$AgentDirName = "{agent_dir_name}"')
            (self.hooks / source.name).write_text(text, encoding="utf-8-sig")
        (self.hooks / "play-tts-windows-sapi.ps1").write_text(FAKE_PROVIDER, encoding="utf-8-sig")
        self.agent_dir = self.home / agent_dir_name
        (self.agent_dir / "TTS-Summary").mkdir(parents=True)
        (self.agent_dir / "TTS-Summary" / "tts-config.txt").write_text(config, encoding="utf-8")
        self.pending = self.agent_dir / "TTS-Summary" / "pending"
        self.shared = self.agent_dir / "tts-summary.txt"
        self.fake_dir = self.home / "fake"
        self.fake_dir.mkdir()
        self.env = dict(os.environ, USERPROFILE=str(self.home), FAKE_TTS_DIR=str(self.fake_dir),
                        TTS_PLAYBACK_QUEUE_NAME="Local\\TtsTest-" + uuid.uuid4().hex)
        for name in ("TTS_SUMMARY", "TTS_NO_PLAY", "TTS_AUDIO_PATH_FILE", "ANTIGRAVITY_CONVERSATION_ID"):
            self.env.pop(name, None)

    def command(self, script: str, *args: str) -> list[str]:
        return [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.hooks / script), *args]

    def run_script(self, script: str, *args: str, payload: str = "", env: dict[str, str] | None = None):
        return subprocess.run(self.command(script, *args), input=payload, env=dict(self.env, **(env or {})),
                              capture_output=True, text=True, encoding="utf-8")

    def session_file(self, session: str) -> Path:
        self.pending.mkdir(parents=True, exist_ok=True)
        return self.pending / f"{session}.txt"

    def calls(self) -> list[tuple[int, int, str]]:
        result = []
        for record in self.fake_dir.glob("call-*.txt"):
            start, end, text = record.read_text(encoding="utf-8").splitlines()[:3]
            result.append((int(start), int(end), text))
        return sorted(result)

    # --- 설정 통지 훅 ---

    def test_context_names_session_file_and_creates_folder(self) -> None:
        self.make_home(".claude")
        completed = self.run_script("tts-config-context.ps1", payload=json.dumps({"session_id": SESSION_A}))
        expected = self.pending / f"{SESSION_A}.txt"
        self.assertIn(f"요약은 이 세션 전용 파일 {expected}에 쓴다.", completed.stdout)
        self.assertTrue(self.pending.is_dir())

    def test_context_falls_back_to_shared_file_without_usable_session(self) -> None:
        self.make_home(".claude")
        for payload in ("", "{}", json.dumps({"session_id": "..\\..\\evil"}), "not json"):
            with self.subTest(payload=payload):
                completed = self.run_script("tts-config-context.ps1", payload=payload)
                self.assertIn("tts-summary.txt를 쓴다.", completed.stdout)
                self.assertNotIn("pending", completed.stdout)

    def test_context_codex_and_agy_shapes(self) -> None:
        self.make_home(".codex")
        codex = json.loads(self.run_script("tts-config-context.ps1", payload=json.dumps({"session_id": SESSION_A})).stdout)
        self.assertIn(f"pending\\{SESSION_A}.txt에 쓴다.", codex["hookSpecificOutput"]["additionalContext"])
        self.make_home(".gemini")
        agy = json.loads(self.run_script("tts-config-context.ps1", payload=json.dumps({"conversationId": SESSION_B})).stdout)
        self.assertIn(f"pending\\{SESSION_B}.txt에 브리핑체 요약을 먼저 쓰고", agy["injectSteps"][0]["ephemeralMessage"])
        from_env = json.loads(self.run_script("tts-config-context.ps1", payload="{}",
                                              env={"ANTIGRAVITY_CONVERSATION_ID": SESSION_A}).stdout)
        self.assertIn(f"pending\\{SESSION_A}.txt", from_env["injectSteps"][0]["ephemeralMessage"])

    # --- Stop 훅: 세션 전용 파일 ---

    def test_stop_plays_own_session_file_and_leaves_others(self) -> None:
        self.make_home(".claude")
        self.session_file(SESSION_A).write_text("에이 세션 요약", encoding="utf-8")
        self.session_file(SESSION_B).write_text("비 세션 요약", encoding="utf-8")
        self.shared.write_text("공용 요약", encoding="utf-8")
        completed = self.run_script("stop-tts.ps1", payload=json.dumps({"session_id": SESSION_A}))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([text for _, _, text in self.calls()], ["에이 세션 요약"])
        self.assertFalse(self.session_file(SESSION_A).exists())
        self.assertEqual(self.session_file(SESSION_B).read_text(encoding="utf-8"), "비 세션 요약")
        self.assertEqual(self.shared.read_text(encoding="utf-8"), "공용 요약")

    def test_korean_payload_keeps_session_id(self) -> None:
        """한글로 끝나는 값이 든 payload(UTF-8)에서도 세션 식별자를 읽는다."""
        self.make_home(".claude")
        self.session_file(SESSION_A).write_text("에이 세션 요약", encoding="utf-8")
        payload = json.dumps({"session_id": SESSION_A, "cwd": "C:\작업\끝", "last_assistant_message": "수정을 마쳤다"},
                             ensure_ascii=False)
        completed = self.run_script("stop-tts.ps1", payload=payload)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([text for _, _, text in self.calls()], ["에이 세션 요약"])

    def test_two_agy_wrappers_both_synthesize(self) -> None:
        """Antigravity wrapper 둘이 동시에 돌아도 두 요약이 모두 합성된다(공용 로그 파일을 다투지 않는다)."""
        self.make_home(".gemini")
        self.session_file(SESSION_A).write_text("에이 대화 요약", encoding="utf-8")
        self.session_file(SESSION_B).write_text("비 대화 요약", encoding="utf-8")
        processes = []
        for session in (SESSION_A, SESSION_B):
            process = subprocess.Popen(self.command("stop-tts-wrapper.ps1"), stdin=subprocess.PIPE,
                                       env=dict(self.env, TTS_NO_PLAY="1"),
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            process.stdin.write(json.dumps({"conversationId": session}).encode("utf-8"))
            process.stdin.close()
            processes.append(process)
        for process in processes:
            self.assertEqual(json.loads(process.stdout.read().decode("utf-8")), {"decision": "proceed"})
            process.stdout.close()
            self.assertEqual(process.wait(timeout=60), 0)
        self.assertEqual(sorted(text for _, _, text in self.calls()), ["비 대화 요약", "에이 대화 요약"])
        self.assertEqual(list(self.pending.glob("*.txt")), [])

    def test_stop_falls_back_to_shared_file(self) -> None:
        self.make_home(".claude")
        self.shared.write_text("공용 요약", encoding="utf-8")
        completed = self.run_script("stop-tts.ps1", payload=json.dumps({"session_id": SESSION_A}))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([text for _, _, text in self.calls()], ["공용 요약"])
        self.assertFalse(self.shared.exists())

    def test_missing_summary_guard_names_session_file(self) -> None:
        self.make_home(".claude")
        self.session_file(SESSION_B).write_text("비 세션 요약", encoding="utf-8")
        completed = self.run_script("stop-tts.ps1", payload=json.dumps({"session_id": SESSION_A}))
        self.assertEqual(completed.returncode, 2)
        self.assertIn(f"pending\\{SESSION_A}.txt 에", completed.stderr)
        self.assertEqual(self.calls(), [])
        self.assertTrue(self.session_file(SESSION_B).exists())
        without_session = self.run_script("stop-tts.ps1", payload="{}")
        self.assertEqual(without_session.returncode, 2)
        self.assertIn("tts-summary.txt 에", without_session.stderr)
        self.assertNotIn("pending", without_session.stderr)

    def test_blank_session_file_is_silent(self) -> None:
        self.make_home(".claude")
        self.session_file(SESSION_A).write_bytes(b"\r\n")
        completed = self.run_script("stop-tts.ps1", payload=json.dumps({"session_id": SESSION_A}))
        self.assertEqual((completed.returncode, completed.stderr), (0, ""))
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.session_file(SESSION_A).exists())

    def test_disabled_clears_own_and_shared_only(self) -> None:
        self.make_home(".claude", config="enabled=off\n")
        self.session_file(SESSION_A).write_text("에이", encoding="utf-8")
        self.session_file(SESSION_B).write_text("비", encoding="utf-8")
        self.shared.write_text("공용", encoding="utf-8")
        completed = self.run_script("stop-tts.ps1", payload=json.dumps({"session_id": SESSION_A}))
        self.assertEqual(completed.returncode, 0)
        self.assertFalse(self.session_file(SESSION_A).exists())
        self.assertFalse(self.shared.exists())
        self.assertTrue(self.session_file(SESSION_B).exists())
        self.assertEqual(self.calls(), [])

    def test_stale_session_files_are_removed(self) -> None:
        self.make_home(".claude")
        stale = self.session_file("stale-session")
        stale.write_text("묵은 요약", encoding="utf-8")
        two_days_ago = stale.stat().st_mtime - 2 * 24 * 3600
        os.utime(stale, (two_days_ago, two_days_ago))
        self.session_file(SESSION_B).write_text("비", encoding="utf-8")
        self.session_file(SESSION_A).write_bytes(b"\r\n")
        self.run_script("stop-tts.ps1", payload=json.dumps({"session_id": SESSION_A}))
        self.assertFalse(stale.exists())
        self.assertTrue(self.session_file(SESSION_B).exists())

    def test_agy_uses_conversation_id(self) -> None:
        self.make_home(".gemini")
        self.session_file(SESSION_A).write_text("대화 요약", encoding="utf-8")
        payload = json.dumps({"conversationId": SESSION_A, "executionNum": 0,
                              "terminationReason": "NO_TOOL_CALL", "fullyIdle": True})
        completed = self.run_script("stop-tts.ps1", payload=payload)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([text for _, _, text in self.calls()], ["대화 요약"])

    # --- 재생 대기열 ---

    def test_two_sessions_play_in_turn_without_loss(self) -> None:
        self.make_home(".claude")
        self.session_file(SESSION_A).write_text("에이 세션 요약", encoding="utf-8")
        self.session_file(SESSION_B).write_text("비 세션 요약", encoding="utf-8")
        processes = []
        for session in (SESSION_A, SESSION_B):
            process = subprocess.Popen(self.command("stop-tts.ps1"), stdin=subprocess.PIPE, env=self.env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            process.stdin.write(json.dumps({"session_id": session}).encode("utf-8"))
            process.stdin.close()
            processes.append(process)
        for process in processes:
            self.assertEqual(process.wait(timeout=60), 0)
        calls = self.calls()
        self.assertEqual(sorted(text for _, _, text in calls), ["비 세션 요약", "에이 세션 요약"])
        self.assertLessEqual(calls[0][1], calls[1][0], "두 재생 구간이 겹쳤다")

    def test_synthesis_only_run_skips_queue_and_reports_audio_path(self) -> None:
        """Antigravity wrapper 경로: 합성 전용 실행은 대기열을 쥐지 않고 음성 파일 경로를 넘겨준다."""
        self.make_home(".gemini")
        self.session_file(SESSION_A).write_text("대화 요약", encoding="utf-8")
        handoff = self.home / "audio-path.txt"
        holder = subprocess.Popen(
            [POWERSHELL, "-NoProfile", "-Command",
             "$m = New-Object System.Threading.Mutex($false, $env:TTS_PLAYBACK_QUEUE_NAME); "
             "[void]$m.WaitOne(); Write-Output held; [void][Console]::In.ReadLine(); $m.ReleaseMutex()"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=self.env, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "held")
            completed = subprocess.run(
                self.command("stop-tts.ps1"), input=json.dumps({"conversationId": SESSION_A}), timeout=60,
                env=dict(self.env, TTS_NO_PLAY="1", TTS_AUDIO_PATH_FILE=str(handoff)),
                capture_output=True, text=True, encoding="utf-8")
        finally:
            holder.stdin.write("\n")
            holder.stdin.close()
            holder.wait(timeout=30)
            holder.stdout.close()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(self.calls()), 1)
        self.assertRegex(handoff.read_text(encoding="utf-8"), r"tts-fake-\d+\.wav$")

    def test_queued_player_waits_for_its_turn(self) -> None:
        self.make_home(".claude")
        audio = self.home / "tts-sample.wav"
        audio.write_bytes(b"RIFF")
        holder = subprocess.Popen(
            [POWERSHELL, "-NoProfile", "-Command",
             "$m = New-Object System.Threading.Mutex($false, $env:TTS_PLAYBACK_QUEUE_NAME); "
             "[void]$m.WaitOne(); Write-Output held; [void][Console]::In.ReadLine(); $m.ReleaseMutex()"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=self.env, text=True)
        player = None
        try:
            self.assertEqual(holder.stdout.readline().strip(), "held")
            player = subprocess.Popen(self.command("play-tts-queued.ps1", "-Path", str(audio)),
                                      env=dict(self.env, TTS_NO_PLAY="1"),
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self.assertRaises(subprocess.TimeoutExpired):
                player.wait(timeout=3)
        finally:
            holder.stdin.write("\n")
            holder.stdin.close()
            holder.wait(timeout=30)
            holder.stdout.close()
        self.assertEqual(player.wait(timeout=30), 0)

    # --- 다시 재생의 공백 억제 파일 ---

    def test_replay_blank_marker_goes_to_session_file(self) -> None:
        self.make_home(".claude")
        completed = self.run_script("tts-replay.ps1", SESSION_A, env={"TTS_REPLAY_DRYRUN": "1"})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.session_file(SESSION_A).read_bytes(), b"\r\n")
        self.assertFalse(self.shared.exists())
        self.make_home(".claude")
        self.run_script("tts-replay.ps1", env={"TTS_REPLAY_DRYRUN": "1"})
        self.assertEqual(self.shared.read_bytes(), b"\r\n")


if __name__ == "__main__":
    unittest.main()
