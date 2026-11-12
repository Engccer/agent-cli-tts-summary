#!/usr/bin/env python3
"""macOS 설정 통지 훅의 에이전트별 출력 계약을 검증한다."""

from __future__ import annotations
import sys
import unittest

if sys.platform != "darwin":
    raise unittest.SkipTest("macOS 전용 스크립트를 실행하는 테스트다")


import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_HOOK = ROOT / "assets" / "macos" / "tts-config-context.sh"


class TtsConfigContextTests(unittest.TestCase):
    def run_hook(
        self,
        agent_dir_name: str,
        config: str | None,
        session_env: dict[str, str] | None = None,
        payload: str = "",
    ) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            if config is not None:
                config_dir = home / agent_dir_name / "TTS-Summary"
                config_dir.mkdir(parents=True)
                (config_dir / "tts-config.txt").write_text(config, encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["AGENT_DIR_NAME"] = agent_dir_name
            for name in ("TTS_SUMMARY", "CLAUDE_CONFIG_DIR", "ANTIGRAVITY_CONVERSATION_ID"):
                env.pop(name, None)
            env.update(session_env or {})
            completed = subprocess.run(
                ["bash", str(CONTEXT_HOOK)],
                input=payload,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.agent_dir = str(home / agent_dir_name)
            self.pending_exists = (home / agent_dir_name / "TTS-Summary" / "pending").is_dir()
            return completed.stdout.strip()

    def codex_message(self, config: str | None, session_env: dict[str, str] | None = None) -> str:
        payload = json.loads(self.run_hook(".codex", config, session_env))
        hook_output = payload["hookSpecificOutput"]
        self.assertEqual(hook_output["hookEventName"], "UserPromptSubmit")
        return hook_output["additionalContext"]

    def agy_message(
        self,
        config: str | None,
        session_env: dict[str, str] | None = None,
        payload: str = '{"invocationNum": 1}',
    ) -> str:
        data = json.loads(self.run_hook(".gemini", config, session_env, payload=payload))
        return data["injectSteps"][0]["ephemeralMessage"]

    def test_codex_emits_additional_context_json(self) -> None:
        self.assertIn(
            "상세 정도 3단계",
            self.codex_message("enabled=on\nverbosity=3\n"),
        )

    def test_codex_disabled_message_is_json(self) -> None:
        self.assertIn("TTS 음성 요약 끔", self.codex_message("enabled=off\n"))

    def test_codex_missing_config_uses_default_verbosity(self) -> None:
        self.assertIn("상세 정도 2단계", self.codex_message(None))

    def test_agy_emits_inject_steps_ephemeral_message_with_summary_path(self) -> None:
        msg = self.agy_message("enabled=on\nverbosity=2\n")
        self.assertIn("[tts-config]", msg)
        self.assertIn("상세 정도 2단계", msg)
        self.assertIn("/.gemini/tts-summary.txt", msg)

    def test_agy_reports_current_settings_on_every_invocation(self) -> None:
        cases = (
            ("enabled=on\nverbosity=3\n", {}, "상세 정도 3단계"),
            ("enabled=off\n", {}, "TTS 음성 요약 끔"),
            ("enabled=on\nverbosity=3\n", {"TTS_SUMMARY": "off"}, "TTS_SUMMARY=off"),
        )
        for config, session_env, expected in cases:
            for invocation in (1, 2, 3):
                with self.subTest(config=config, session_env=session_env, invocation=invocation):
                    data = json.loads(self.run_hook(
                        ".gemini", config, session_env,
                        payload=json.dumps({"invocationNum": invocation}),
                    ))
                    self.assertEqual(set(data), {"injectSteps"})
                    self.assertEqual(len(data["injectSteps"]), 1)
                    self.assertEqual(set(data["injectSteps"][0]), {"ephemeralMessage"})
                    message = data["injectSteps"][0]["ephemeralMessage"]
                    self.assertTrue(message.startswith("[tts-config]"))
                    self.assertEqual(len(message.splitlines()), 1)
                    self.assertIn(expected, message)
                    if config.startswith("enabled=off") or session_env:
                        self.assertIn("쓰지 않는다", message)
                        self.assertNotIn("상세 정도", message)
                    else:
                        self.assertIn("/.gemini/tts-summary.txt", message)

    def test_claude_keeps_plain_text_contract(self) -> None:
        output = self.run_hook(".claude", "enabled=on\nverbosity=1\n")
        self.assertTrue(output.startswith("[tts-config]"))
        self.assertIn("상세 정도 1단계", output)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(output)

    def test_session_id_in_payload_names_session_summary_file(self) -> None:
        """세션 식별자를 알면 그 세션 전용 파일 경로를 알리고 폴더를 미리 만든다."""
        config = "enabled=on\nverbosity=2\n"
        detail = "2단계(3~6문장, 과정과 결정 포함)"
        output = self.run_hook(".claude", config, payload='{"session_id": "abc-123_X", "prompt": "안녕"}')
        self.assertEqual(output, f"[tts-config] TTS 음성 요약 켬, 상세 정도 {detail}. "
                                 f"요약은 이 세션 전용 파일 {self.agent_dir}/TTS-Summary/pending/abc-123_X.txt에 쓴다.")
        self.assertTrue(self.pending_exists)

        data = json.loads(self.run_hook(".codex", config, payload='{"session_id": "019a-codex"}'))
        self.assertEqual(data["hookSpecificOutput"]["additionalContext"],
                         f"[tts-config] TTS 음성 요약 켬, 상세 정도 {detail}. "
                         f"요약은 이 세션 전용 파일 {self.agent_dir}/TTS-Summary/pending/019a-codex.txt에 쓴다.")

        expected = (f"[tts-config] TTS 음성 요약 켬, 상세 정도 {detail}. 응답을 마치기 전에 이 세션 전용 파일 "
                    "{}/TTS-Summary/pending/conv-1.txt에 브리핑체 요약을 먼저 쓰고 본문 답변을 마지막으로 낸다.")
        message = self.agy_message(config, payload='{"invocationNum": 1, "conversationId": "conv-1"}')
        self.assertEqual(message, expected.format(self.agent_dir))
        self.assertTrue(self.pending_exists)
        # payload에 없으면 Antigravity는 환경 변수의 대화 식별자를 쓴다.
        message = self.agy_message(config, {"ANTIGRAVITY_CONVERSATION_ID": "conv-1"})
        self.assertEqual(message, expected.format(self.agent_dir))

    def test_unknown_or_unsafe_session_id_keeps_shared_summary_file(self) -> None:
        """식별자가 없거나 경로에 쓸 수 없는 값이면 공용 파일을 쓰게 하고 폴더도 만들지 않는다."""
        config = "enabled=on\nverbosity=1\n"
        legacy = "[tts-config] TTS 음성 요약 켬, 상세 정도 1단계(1~2문장, 결과만). tts-summary.txt를 쓴다."
        payloads = ["", "{}", "깨진 JSON", "[1, 2]", json.dumps({"session_id": "../evil"}),
                    json.dumps({"session_id": "a/b"}), json.dumps({"session_id": "a b"}),
                    json.dumps({"session_id": "a\n"}), json.dumps({"session_id": "x" * 129}),
                    json.dumps({"session_id": 123}), json.dumps({"tool_input": {"session_id": "nested"}}),
                    json.dumps({"session_id": "../evil", "conversationId": "good"})]
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertEqual(self.run_hook(".claude", config, payload=payload), legacy)
                self.assertFalse(self.pending_exists)
        # Claude·Codex는 Antigravity 환경 변수를 보지 않는다.
        self.assertEqual(self.run_hook(".claude", config, {"ANTIGRAVITY_CONVERSATION_ID": "conv-1"}), legacy)
        self.assertEqual(self.run_hook(".claude", config, payload=json.dumps({"session_id": "x" * 128})),
                         legacy.replace("tts-summary.txt를 쓴다.", "요약은 이 세션 전용 파일 "
                                        f"{self.agent_dir}/TTS-Summary/pending/{'x' * 128}.txt에 쓴다."))

    def test_disabled_or_muted_does_not_name_session_file(self) -> None:
        payload = '{"session_id": "abc"}'
        self.assertEqual(self.run_hook(".claude", "enabled=off\n", payload=payload),
                         "[tts-config] TTS 음성 요약 끔. tts-summary.txt를 쓰지 않는다.")
        self.assertFalse(self.pending_exists)
        self.assertNotIn("pending", self.run_hook(".claude", "enabled=on\n", {"TTS_SUMMARY": "off"}, payload))
        self.assertFalse(self.pending_exists)

    def test_session_mute_env_overrides_enabled_config(self) -> None:
        """병렬 작업 세션(TTS_SUMMARY=off)은 설정이 켬이어도 쓰지 않는다고 알리고, 보고 경로를 함께 준다."""
        output = self.run_hook(".claude", "enabled=on\nverbosity=3\n", {"TTS_SUMMARY": "off"})
        self.assertTrue(output.startswith("[tts-config]"))
        self.assertIn("쓰지 않는다", output)
        self.assertIn("코디네이터", output)
        self.assertNotIn("상세 정도", output)
        self.assertIn("쓰지 않는다", self.codex_message("enabled=on\n", {"TTS_SUMMARY": "OFF"}))

    def test_session_mute_env_other_values_keep_config(self) -> None:
        output = self.run_hook(".claude", "enabled=on\nverbosity=1\n", {"TTS_SUMMARY": "on"})
        self.assertIn("상세 정도 1단계", output)


if __name__ == "__main__":
    unittest.main()
