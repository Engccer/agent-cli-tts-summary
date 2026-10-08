#!/usr/bin/env python3
"""합성 기록으로 세션 격리, 완료 증거, 되감기와 낭독 제어 턴을 검증한다."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tts_transcripts", ROOT / "assets/macos/tts_transcripts.py")
transcripts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transcripts)


def event(kind, **payload):
    return {"type": "event_msg", "payload": {"type": kind, **payload}}


def message(role, text, **payload):
    return {"type": "response_item", "payload": {
        "type": "message", "role": role,
        "content": [{"type": "input_text" if role == "user" else "output_text", "text": text}],
        **payload}}


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.agent = Path(temp.name)
        self.session = "session-123"
        self.codex = self.agent / "sessions/2026/10/09" / f"rollout-2026-10-09T00-00-00-{self.session}.jsonl"
        self.agy = (self.agent / "antigravity-cli/brain" / self.session
                    / ".system_generated/logs/transcript_full.jsonl")
        self.rows = [{"type": "session_meta", "payload": {"id": self.session}}]

    def save(self, path=None, rows=None):
        path = path or self.codex
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                for row in (self.rows if rows is None else rows)), encoding="utf-8")

    def turn(self, identifier, answer=None, user="일반 요청", complete=True):
        self.rows.extend([event("task_started", turn_id=identifier), message("user", user),
                          {"type": "turn_context", "payload": {"turn_id": identifier}}])
        if answer is not None:
            self.rows.append(message("assistant", answer, phase="final_answer"))
        if complete:
            self.rows.append(event("task_complete", turn_id=identifier,
                                   last_agent_message="인용과 서식이 제거된 다른 본문"))

    def read(self):
        return transcripts.last_codex_response(self.agent, self.session)

    def agy_rows(self, *contents):
        return [{"step_index": i, "source": "USER_EXPLICIT" if kind == "USER_INPUT" else "MODEL",
                 "type": kind, "status": "DONE", "content": text, **extra}
                for i, (kind, text, extra) in enumerate(contents)]

    def test_codex_preserves_original_and_only_final_output_text(self):
        original = "# 제목\n\n[출처](https://example.com) citesource\n\n```py\nx = 1\n```"
        self.turn("turn-1", complete=False)
        self.rows.extend([message("assistant", "중간 보고", phase="commentary"),
                          {"type": "response_item", "payload": {"type": "agent_message", "content": "팀원 응답"}},
                          {"type": "response_item", "payload": {"type": "function_call_output", "output": "도구 결과"}},
                          message("assistant", original, phase="final_answer")])
        self.rows[-1]["payload"]["content"].append({"type": "reasoning", "text": "생각"})
        self.rows.append(event("task_complete", turn_id="turn-1", last_agent_message="변형된 본문"))
        self.save()
        self.assertEqual(self.read(), original)

    def test_codex_unfinished_turn_and_mismatched_completion_are_excluded(self):
        self.turn("turn-1", "완료 응답")
        self.turn("turn-2", "미완료 응답", complete=False)
        self.rows.append(event("task_complete", turn_id="wrong-turn"))
        self.save()
        with self.codex.open("ab") as stream:
            stream.write(b'{"type":"event_msg","payload":')
        self.assertEqual(self.read(), "완료 응답")

    def test_codex_rollback_counts_user_turns_and_ignores_abandoned_answer(self):
        self.turn("turn-1", "유지 응답")
        self.turn("turn-2", "버린 응답")
        self.turn("turn-3", "버린 제어 응답", user="/tts-read")
        self.rows.append(event("thread_rolled_back", num_turns=2))
        self.save()
        self.assertEqual(self.read(), "유지 응답")
        self.turn("turn-4", "새 가지 응답")
        self.save()
        self.assertEqual(self.read(), "새 가지 응답")

    def test_codex_fork_reads_only_history_copied_into_current_file(self):
        self.turn("inherited-turn", "복제된 응답")
        self.rows[0]["payload"]["forked_from_id"] = "parent-session"
        self.save()
        parent = self.codex.with_name("rollout-2026-10-09T01-00-00-parent-session.jsonl")
        self.save(parent, [{"type": "session_meta", "payload": {"id": "parent-session"}},
                           message("assistant", "부모 세션의 나중 응답", phase="final_answer")])
        self.assertEqual(self.read(), "복제된 응답")

    def test_codex_control_commands_and_skill_messages_are_excluded(self):
        self.turn("turn-1", "정상 응답")
        for i, command in enumerate(("/tts-read", "/tts replay", "/tts-pause",
                                     "$codex-tts-read", "$codex-tts-replay", "$codex-tts-pause",
                                     "<command-name>/codex-tts-read</command-name>",
                                     "<command-name>$codex-tts-read</command-name>",
                                     "<skill>\n<name>codex-tts-read</name>\n본문</skill>",
                                     "<skill-name>codex-tts-read</skill-name>\n본문",
                                     "[$codex-tts-read](/tmp/codex-tts-read/SKILL.md)")):
            self.turn(f"control-{i}", complete=False, user=command)
            self.rows.append(message("user", "스킬 본문"))
            self.rows.extend([message("assistant", "실행 확인 응답", phase="final_answer"),
                              event("task_complete", turn_id=f"control-{i}")])
        self.save()
        self.assertEqual(self.read(), "정상 응답")

    def test_control_name_mentioned_in_normal_prose_is_not_a_command(self):
        for text in ("$codex-tts-read 명령의 구현을 검토해 줘", "`/tts-read`는 어떻게 작동해?",
                     "예시: [$codex-tts-read](/tmp/SKILL.md)"):
            self.assertFalse(transcripts.is_control_command(text))

    def test_natural_language_control_marker_persists_without_content(self):
        self.turn("turn-1", "개인정보를 담은 정상 응답")
        self.turn("turn-control", user="이 답변을 다시 읽어 줘", complete=False)
        self.save()
        transcripts.mark_control_turn(self.agent, "codex", self.session)
        self.rows.extend([message("assistant", "읽기 실행 확인", phase="final_answer"),
                          event("task_complete", turn_id="turn-control")])
        self.save()
        self.assertEqual(self.read(), "개인정보를 담은 정상 응답")
        marker = self.agent / "TTS-Summary/control-turns/session-123.json"
        self.assertEqual(json.loads(marker.read_text()), {
            "agent": "codex", "session_id": self.session, "turn_ids": ["turn-control"]})

    def test_direct_shell_control_after_completion_keeps_normal_answer(self):
        self.turn("turn-1", "완료 응답")
        self.save()
        transcripts.mark_control_turn(self.agent, "codex", self.session)
        self.assertEqual(self.read(), "완료 응답")
        self.assertFalse((self.agent / "TTS-Summary/control-turns").exists())

    def test_session_validation_does_not_fall_back_to_another_session(self):
        self.turn("turn-1", "응답")
        self.save()
        for identifier in ("", "../session-123", "missing-session"):
            for reader in (transcripts.last_codex_response, transcripts.last_agy_response):
                with self.subTest(identifier=identifier, reader=reader.__name__), self.assertRaises(ValueError):
                    reader(self.agent, identifier)
        duplicate = self.agent / "sessions/another" / self.codex.name
        self.save(duplicate)
        with self.assertRaises(ValueError):
            self.read()
        duplicate.unlink()
        self.rows[0]["payload"]["id"] = "other"
        self.save()
        with self.assertRaises(ValueError):
            self.read()

    def test_corrupt_middle_row_is_rejected_but_partial_tail_is_safe(self):
        self.turn("turn-1", "완료 응답")
        self.save()
        with self.codex.open("ab") as stream:
            stream.write(b'not-json\n')
        with self.assertRaises(ValueError):
            self.read()

    def test_codex_last_final_before_completion_is_one_original_response(self):
        self.turn("turn-1", "첫 응답", complete=False)
        self.rows.extend([message("assistant", "둘째 응답", phase="final_answer"),
                          event("task_complete", turn_id="turn-1")])
        self.save()
        self.assertEqual(self.read(), "둘째 응답")

    def test_codex_stop_hook_reentry_keeps_last_completed_final(self):
        self.turn("turn-1", "첫 완료 응답")
        self.rows.extend([event("task_started", turn_id="turn-1"),
                          message("assistant", "재개 후 미완료 응답", phase="final_answer")])
        self.save()
        self.assertEqual(self.read(), "첫 완료 응답")
        self.rows.append(event("task_complete", turn_id="turn-1"))
        self.save()
        self.assertEqual(self.read(), "재개 후 미완료 응답")

    def test_agy_selects_final_content_excluding_tools_thinking_and_running(self):
        original = "원문 **그대로**\n\n[출처](https://example.com)"
        rows = self.agy_rows(("USER_INPUT", "요청", {}),
                            ("PLANNER_RESPONSE", "도구 실행 설명", {"tool_calls": [{"name": "tool"}]}),
                            ("GENERIC", "도구 결과", {}),
                            ("PLANNER_RESPONSE", original, {"thinking": "비공개 사고", "tool_calls": []}),
                            ("USER_INPUT", "다음 요청", {}),
                            ("PLANNER_RESPONSE", "미완료", {"status": "RUNNING"}))
        self.save(self.agy, rows)
        self.assertEqual(transcripts.last_agy_response(self.agent, self.session), original)

    def test_agy_last_completed_planner_after_system_continuation(self):
        rows = self.agy_rows(("USER_INPUT", "요청", {}),
                            ("PLANNER_RESPONSE", "초기 응답", {}),
                            ("SYSTEM_MESSAGE", "계속", {"source": "SYSTEM"}),
                            ("PLANNER_RESPONSE", "마지막 완료 응답", {}))
        self.save(self.agy, rows)
        self.assertEqual(transcripts.last_agy_response(self.agent, self.session), "마지막 완료 응답")

    def test_agy_control_commands_and_natural_language_markers(self):
        rows = self.agy_rows(("USER_INPUT", "정상 요청", {}),
                            ("PLANNER_RESPONSE", "정상 응답", {}),
                            ("USER_INPUT", "/tts replay", {}),
                            ("PLANNER_RESPONSE", "반복 재생 확인", {}),
                            ("USER_INPUT", "잠깐 멈춰 줘", {}),
                            ("PLANNER_RESPONSE", "도구 실행", {"tool_calls": [{"name": "pause"}]}))
        self.save(self.agy, rows)
        transcripts.mark_control_turn(self.agent, "agy", self.session)
        rows.append({"step_index": 6, "source": "MODEL", "type": "PLANNER_RESPONSE",
                     "status": "DONE", "content": "멈춤 확인"})
        self.save(self.agy, rows)
        self.assertEqual(transcripts.last_agy_response(self.agent, self.session), "정상 응답")
        marker = self.agent / "TTS-Summary/control-turns/session-123.json"
        self.assertEqual(json.loads(marker.read_text())["turn_ids"], [4])

    def test_agy_duplicate_steps_rejected_and_partial_tail_ignored(self):
        rows = self.agy_rows(("USER_INPUT", "요청", {}), ("PLANNER_RESPONSE", "완료 응답", {}))
        self.save(self.agy, rows)
        with self.agy.open("ab") as stream:
            stream.write(b'{"step_index":')
        self.assertEqual(transcripts.last_agy_response(self.agent, self.session), "완료 응답")
        rows.append(rows[-1])
        self.save(self.agy, rows)
        with self.assertRaises(ValueError):
            transcripts.last_agy_response(self.agent, self.session)

    def test_corrupt_marker_rejected(self):
        self.turn("turn-1", "응답")
        self.save()
        path = self.agent / "TTS-Summary/control-turns/session-123.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"turn_ids": ["wrong-session"]}')
        with self.assertRaises(ValueError):
            self.read()

    def test_mark_cli_success_and_stderr_failure(self):
        self.turn("turn-control", complete=False)
        self.save()
        command = [sys.executable, str(ROOT / "assets/macos/tts_transcripts.py"), "mark",
                   "--agent", "codex", "--agent-dir", str(self.agent), "--session-id"]
        success = subprocess.run(command + [self.session], capture_output=True, text=True)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertEqual(success.stdout, "")
        failure = subprocess.run(command + ["missing"], capture_output=True, text=True)
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(failure.stdout, "")
        self.assertIn("낭독 제어 턴을 기록하지 못했습니다", failure.stderr)


if __name__ == "__main__":
    unittest.main()
