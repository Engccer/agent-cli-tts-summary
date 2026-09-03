#!/usr/bin/env python3
"""Windows 판 질문 선택지 안내·중간 phase 보고가 macOS 판과 같은 계약을 지키는지 검증한다.
PowerShell이 있는 환경(Windows)에서만 돌고, 없으면 건너뛴다.
실행: python scripts/test_tts_interim_windows.py
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "assets" / "windows"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
QUESTION = {
    "tool_name": "AskUserQuestion",
    "tool_input": {"questions": [{"question": "어느 쪽으로 할까요?", "header": "방식",
                                  "options": [{"label": "A안"}, {"label": "B안"}]}]},
}
HEADER_ONLY = {
    "tool_name": "request_user_input",
    "tool_input": {"questions": [{"header": "배포 방식", "options": [{"label": "지금"}, {"label": "나중에"}]},
                                 {"question": "테스트도 돌릴까요?", "options": [{"label": "예"}]}]},
}


@unittest.skipUnless(POWERSHELL, "PowerShell이 없는 환경")
class WindowsInterimGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="tts-interim-win-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.hooks = self.home / "hooks"
        self.hooks.mkdir()
        for name in ("tts-config.ps1", "ask-question-tts.ps1", "play-tts-briefing.ps1"):
            shutil.copy(WINDOWS / name, self.hooks / name)
        self.config = self.home / ".claude" / "TTS-Summary" / "tts-config.txt"
        self.config.parent.mkdir(parents=True)

    def write_config(self, **values: str) -> None:
        self.config.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")

    def run_script(self, name: str, *args: str, stdin: dict | None = None, **extra_env: str) -> str:
        env = dict(os.environ, USERPROFILE=str(self.home), **extra_env)
        payload = json.dumps(stdin, ensure_ascii=False).encode("utf-8") if stdin is not None else None
        completed = subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.hooks / name), *args],
            input=payload, env=env, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        return completed.stdout.decode("utf-8", "replace").strip()

    def test_question_hook_speaks_only_when_interim_on(self) -> None:
        self.write_config(enabled="on", interim="on")
        out = self.run_script("ask-question-tts.ps1", stdin=QUESTION, ASK_TTS_DRYRUN="1")
        self.assertEqual(out, "질문: 어느 쪽으로 할까요? 선택지는 A안, B안, 그리고 기타 직접 입력입니다.")
        self.write_config(enabled="on", interim="off")
        self.assertEqual(self.run_script("ask-question-tts.ps1", stdin=QUESTION, ASK_TTS_DRYRUN="1"), "")
        self.write_config(enabled="off", interim="on")
        self.assertEqual(self.run_script("ask-question-tts.ps1", stdin=QUESTION, ASK_TTS_DRYRUN="1"), "")

    def test_header_fallback_and_numbering(self) -> None:
        self.write_config(enabled="on", interim="on")
        out = self.run_script("ask-question-tts.ps1", stdin=HEADER_ONLY, ASK_TTS_DRYRUN="1")
        self.assertIn("1번 질문: 배포 방식 선택지는 지금, 나중에, 그리고 기타 직접 입력입니다.", out)
        self.assertIn("2번 질문: 테스트도 돌릴까요? 선택지는 예, 그리고 기타 직접 입력입니다.", out)

    def test_briefing_speaks_only_when_interim_on(self) -> None:
        self.write_config(enabled="on", interim="on", speed="7")
        out = self.run_script("play-tts-briefing.ps1", "1단계 완료", BRIEFING_TTS_DRYRUN="1")
        self.assertIn("rate=4", out)
        self.assertIn("text=1단계 완료", out)
        self.write_config(enabled="on", interim="off")
        self.assertEqual(self.run_script("play-tts-briefing.ps1", "보고", BRIEFING_TTS_DRYRUN="1"), "")

    def test_missing_key_defaults_to_off_on_windows(self) -> None:
        self.write_config(enabled="on")
        self.assertEqual(self.run_script("play-tts-briefing.ps1", "보고", BRIEFING_TTS_DRYRUN="1"), "")


if __name__ == "__main__":
    unittest.main()
