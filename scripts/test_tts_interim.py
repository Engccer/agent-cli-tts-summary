#!/usr/bin/env python3
"""interim 설정이 질문 선택지 안내와 중간 phase 보고를 결정론적으로 막는지 검증한다."""

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MACOS = ROOT / "assets" / "macos"
QUESTION = {
    "tool_name": "AskUserQuestion",
    "tool_input": {"questions": [{"question": "어느 쪽으로 할까요?", "header": "방식",
                                  "options": [{"label": "A안"}, {"label": "B안"}]}]},
}


class InterimGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="tts-interim-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        # ask-question-tts.sh 템플릿은 .codex 기본값이라 그 폴더에 설정을 둔다.
        self.config = self.home / ".codex" / "TTS-Summary" / "tts-config.txt"
        self.config.parent.mkdir(parents=True)

    def write_config(self, **values: str) -> None:
        self.config.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")

    def run_script(self, name: str, *args: str, stdin: str = "", **extra_env: str) -> str:
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=".codex", **extra_env)
        completed = subprocess.run(["bash", str(MACOS / name), *args], input=stdin,
                                   env=env, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout

    def test_question_hook_speaks_only_when_interim_on(self) -> None:
        payload = json.dumps(QUESTION, ensure_ascii=False)
        self.write_config(enabled="on", interim="on")
        self.assertIn("A안", self.run_script("ask-question-tts.sh", stdin=payload, ASK_TTS_DRYRUN="1"))
        self.write_config(enabled="on", interim="off")
        self.assertEqual(self.run_script("ask-question-tts.sh", stdin=payload, ASK_TTS_DRYRUN="1"), "")
        self.write_config(enabled="off", interim="on")
        self.assertEqual(self.run_script("ask-question-tts.sh", stdin=payload, ASK_TTS_DRYRUN="1"), "")

    def test_briefing_speaks_only_when_interim_on(self) -> None:
        self.write_config(enabled="on", interim="on")
        self.assertIn("text=1단계 완료", self.run_script("play-tts-briefing.sh", "1단계 완료", BRIEFING_TTS_DRYRUN="1"))
        self.write_config(enabled="on", interim="off")
        self.assertEqual(self.run_script("play-tts-briefing.sh", "1단계 완료", BRIEFING_TTS_DRYRUN="1"), "")

    def test_missing_key_defaults_to_on(self) -> None:
        self.write_config(enabled="on")
        self.assertIn("text=", self.run_script("play-tts-briefing.sh", "보고", BRIEFING_TTS_DRYRUN="1"))


if __name__ == "__main__":
    unittest.main()
