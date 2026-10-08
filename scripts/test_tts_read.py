#!/usr/bin/env python3
"""전문 보존, 세션 선택, 코드 제외, Stop hook 억제 계약을 검증한다."""

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tts_read", ROOT / "assets/macos/tts-read.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.agent = self.home / ".claude"
        self.path = self.agent / "projects/project/session-123.jsonl"
        self.path.parent.mkdir(parents=True)
        self.rows = []

    def add(self, kind, content, stop=None, **extra):
        row = {"type": kind, "uuid": str(len(self.rows)),
               "parentUuid": self.rows[-1]["uuid"] if self.rows else None,
               "message": {"role": kind, "content": content, "stop_reason": stop}}
        row.update(extra)
        self.rows.append(row)
        return row

    def save(self):
        self.path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in self.rows) + "\n", encoding="utf-8")

    def answer(self, text, **extra):
        return self.add("assistant", [{"type": "text", "text": text}], "end_turn", **extra)

    def test_only_completed_response_excludes_summary_tools_and_progress(self):
        self.add("user", "요청")
        self.add("assistant", [{"type": "text", "text": "중간 보고"}], "tool_use")
        self.add("assistant", [{"type": "tool_use", "name": "Write", "input": {
            "file_path": "~/.claude/tts-summary.txt", "content": "읽으면 안 되는 요약"}}], "tool_use")
        self.add("user", [{"type": "tool_result", "content": "요약 도구 결과"}])
        original = "# 제목\n\n그대로 읽을 문장. **강조**와 `값`.\n\n|열|값|\n|---|---|\n|가|나|\n[출처](https://example.com)"
        self.answer(original)
        self.add("user", "/tts-read")
        self.save()
        self.assertEqual(reader.speech_text(reader.last_response(self.path)), original)

    def test_repeat_read_and_replay_skip_their_confirmation(self):
        self.answer("응답 전문")
        self.add("user", "<command-name>/tts-read</command-name>")
        self.add("user", "스킬 본문", isMeta=True)
        self.answer("마지막 응답을 읽습니다.")
        self.add("user", "/tts-replay")
        self.answer("다시 재생합니다.")
        self.add("user", "/tts-read")
        self.save()
        self.assertEqual(reader.last_response(self.path), "응답 전문")

    def test_rewind_ignores_abandoned_branch_and_sidechain(self):
        first = self.add("user", "첫 요청")
        self.answer("버린 응답")
        self.add("user", "고친 요청", parentUuid=first["uuid"])
        final = self.answer("고친 응답")
        self.answer("다른 에이전트 응답", isSidechain=True)
        self.add("user", "/tts-read", parentUuid=final["uuid"])
        self.save()
        self.assertEqual(reader.last_response(self.path), "고친 응답")

    def test_split_message_blocks_are_all_read(self):
        a = self.answer("첫 문단")
        a["message"]["id"] = "message-1"
        b = self.answer("둘째 문단")
        b["message"]["id"] = "message-1"
        self.save()
        self.assertEqual(reader.last_response(self.path), "첫 문단\n\n둘째 문단")

    def test_unfinished_and_api_error_do_not_replace_answer(self):
        self.answer("완료 응답")
        self.add("assistant", [{"type": "text", "text": "아직 생성 중"}])
        self.answer("API 오류", isApiErrorMessage=True)
        self.save()
        with self.path.open("a") as f:
            f.write('{"type":')
        self.assertEqual(reader.last_response(self.path), "완료 응답")

    def test_fences_and_language_labels(self):
        cases = [
            ("전\n```python\nprint('비밀')\n```\n후", "전\npython 코드 블록입니다.\n후"),
            ("전\n~~~json\n{}\n~~~\n후", "전\njson 코드 블록입니다.\n후"),
            ("```\n비밀\n```", "코드 블록입니다.\n"),
            ("````markdown\n```python\n비밀\n```\n````\n후", "markdown 코드 블록입니다.\n후"),
            ("> ```sh\n> 비밀\n> ```\n후", "sh 코드 블록입니다.\n후"),
            ("- ```js\n  비밀\n  ```\n후", "js 코드 블록입니다.\n후"),
            ("```bash\n닫히지 않은 코드", "bash 코드 블록입니다.\n"),
            ("전\n\n    비밀 코드\n    둘째 줄\n\n후", "전\n\n코드 블록입니다.\n\n후"),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                self.assertEqual(reader.speech_text(original), expected)

    def test_current_session_only_and_ambiguous_copy_rejected(self):
        self.answer("응답")
        self.save()
        self.assertEqual(reader.find_transcript(self.agent, "session-123"), self.path)
        for value in ("", "../session-123", "missing"):
            with self.assertRaises(ValueError):
                reader.find_transcript(self.agent, value)
        duplicate = self.agent / "projects/another/session-123.jsonl"
        duplicate.parent.mkdir()
        duplicate.write_text(self.path.read_text())
        with self.assertRaises(ValueError):
            reader.find_transcript(self.agent, "session-123")

    def test_list_prose_and_nested_lists_are_not_code(self):
        original = "1. 항목\n\n    중요한 설명입니다.\n\n    - 하위 목록\n\n      하위 설명\n\n다음 문장"
        self.assertEqual(reader.speech_text(original), original)

    def test_fence_ends_with_quote_or_list_container(self):
        for original in (
            "> ```python\n> print(1)\n\n반드시 읽어야 할 결론입니다.",
            "- ```python\n  print(1)\n\n반드시 읽어야 할 결론입니다.",
        ):
            with self.subTest(original=original):
                result = reader.speech_text(original)
                self.assertIn("python 코드 블록입니다.", result)
                self.assertNotIn("print(1)", result)
                self.assertIn("반드시 읽어야 할 결론입니다.", result)

    def test_inline_fence_and_paragraph_continuations_are_preserved(self):
        for original in ("```인라인 코드```", "문장\n    같은 문단 설명", "- 설명\n    이어지는 문장"):
            self.assertEqual(reader.speech_text(original), original)

    def test_quote_symbols_inside_code_do_not_close_fence(self):
        for original in ("```text\n> ```\n이 줄도 코드\n```\n결론",
                         "> ```text\n> > ```\n> 이 줄도 코드\n> ```\n결론"):
            self.assertEqual(reader.speech_text(original), "text 코드 블록입니다.\n결론")

    def test_fences_in_nested_containers(self):
        for original in ("- > ```python\n  > print(1)\n  > ```\n\n결론",
                         "> - ```python\n>   print(1)\n>   ```\n\n결론"):
            self.assertEqual(reader.speech_text(original), "python 코드 블록입니다.\n\n결론")

    def test_original_line_endings_and_unicode_prose_are_preserved(self):
        original = "전\r\n\r\n```python\r\nprint(1)\r\n```\r\n\r\n후\u2028끝"
        self.assertEqual(reader.speech_text(original), "전\r\n\r\npython 코드 블록입니다.\n\r\n후\u2028끝")

    def run_shell(self, **env):
        return subprocess.run(["bash", str(ROOT / "assets/macos/tts-read.sh"), "session-123"],
                              env={**os.environ, "HOME": str(self.home), "CLAUDE_CONFIG_DIR": str(self.agent),
                                   "TTS_READ_DRYRUN": "1", "TTS_SUMMARY": "on", **env},
                              capture_output=True, text=True, check=True)

    def test_shell_uses_settings_suppresses_summary_preserves_archive(self):
        self.answer("긴 응답입니다.\n" * 20000)
        self.save()
        config = self.agent / "TTS-Summary"
        config.mkdir()
        (config / "tts-config.txt").write_text("enabled=off\ninterim=off\nvoice_say=Test Voice\nspeed=7.5\n")
        result = json.loads(self.run_shell().stdout)
        self.assertEqual(result["voice"], "Test Voice")
        self.assertEqual(result["rate"], 400)
        self.assertEqual(result["text"], "긴 응답입니다.\n" * 20000)
        self.assertEqual((self.agent / "tts-summary.txt").read_text(), "\n")
        self.assertFalse((config / "wav").exists())

    def test_empty_transcript_and_muted_session(self):
        self.save()
        summary = self.agent / "tts-summary.txt"
        summary.write_text("다른 세션 요약")
        self.assertIn("완료 응답이 없습니다", self.run_shell(TTS_SUMMARY="off").stdout)
        self.assertEqual(summary.read_text(), "다른 세션 요약")
        self.run_shell()
        self.assertEqual(summary.read_text(), "\n")

    def test_stop_hook_consumes_suppression_without_new_audio(self):
        self.answer("완료 응답")
        self.save()
        self.run_shell()
        hooks = self.agent / "hooks"
        hooks.mkdir()
        (hooks / "tts-config.sh").write_bytes((ROOT / "assets/macos/tts-config.sh").read_bytes())
        stop = (ROOT / "assets/macos/stop-tts.sh").read_text().replace('AGENT_DIR_NAME=".codex"', 'AGENT_DIR_NAME=".claude"')
        (hooks / "stop-tts.sh").write_text(stop)
        result = subprocess.run(["bash", str(hooks / "stop-tts.sh")], input='{"stop_hook_active":false}',
                                env={**os.environ, "HOME": str(self.home), "TTS_SUMMARY": "on"},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.agent / "tts-summary.txt").exists())
        self.assertFalse((self.agent / "TTS-Summary/wav").exists())

    def test_speech_uses_file_descriptor_without_body_in_argv(self):
        captured = {}
        def launch(args, **kwargs):
            captured["args"] = args
            captured["text"] = kwargs["stdin"].read().decode()
            captured["detached"] = kwargs["start_new_session"]
            class Process:
                def wait(self, timeout):
                    raise subprocess.TimeoutExpired(args, timeout)
            return Process()
        with patch.object(reader.subprocess, "Popen", side_effect=launch):
            reader.speak("응답 전문", "Test Voice", 400, self.agent)
        self.assertEqual(captured["text"], "응답 전문")
        self.assertNotIn("응답 전문", captured["args"])
        self.assertIn("--speak", captured["args"])
        self.assertTrue(captured["detached"])

    def test_worker_cleans_text_file_after_success_and_failure(self):
        for code in (0, 1):
            captured = {}
            def run(args, **kwargs):
                path = Path(args[args.index("-f") + 1])
                captured["path"] = path
                self.assertEqual(path.read_text(), "응답 전문")
                return subprocess.CompletedProcess(args, code)
            with patch.object(reader.sys, "stdin") as stream, patch.object(reader.subprocess, "run", side_effect=run):
                stream.buffer = io.BytesIO("응답 전문".encode())
                self.assertEqual(reader.play_stdin("Test Voice", 400), code)
            self.assertFalse(captured["path"].exists())


if __name__ == "__main__":
    unittest.main()
