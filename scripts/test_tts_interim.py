#!/usr/bin/env python3
"""interim 설정이 질문 선택지 안내와 중간 phase 보고를 결정론적으로 막는지 검증한다."""

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MACOS = ROOT / "assets" / "macos"
QUESTION = {
    "tool_name": "AskUserQuestion",
    "tool_input": {"questions": [{"question": "어느 쪽으로 할까요?", "header": "방식",
                                  "options": [{"label": "A안"}, {"label": "B안"}]}]},
}


def without_live_audio(command: list[str]) -> list[str]:
    """재생 경로가 회귀해도 테스트가 실제 음성·launchd·API에 도달하지 않게 한다."""
    if sys.platform == 'darwin' and shutil.which('sandbox-exec'):
        policy = ('(version 1)(allow default)(deny network*)'
                  '(deny process-exec (literal "/usr/bin/say")'
                  '(literal "/usr/bin/afplay")(literal "/bin/launchctl"))')
        return ['sandbox-exec', '-p', policy, *command]
    return command


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
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME=".codex", TTS_SUMMARY="on") | extra_env
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

    def test_codex_briefing_dispatches_selected_provider_through_worker(self) -> None:
        hooks = self.home / '.codex/hooks-macos'
        shutil.copytree(MACOS, hooks)
        calls = self.home / 'calls.json'
        (hooks / 'tts_playback.py').write_text(
            'import json,sys\nfrom pathlib import Path\n'
            f'Path({str(calls)!r}).write_text(json.dumps({{"args":sys.argv[1:],"text":sys.stdin.read()}}))\n')
        self.write_config(enabled='on', interim='on', provider='azure-api', voice_azure='ko-KR-YuJinNeural')
        result = subprocess.run(without_live_audio(['bash', str(hooks / 'play-tts-briefing.sh'), '진행 보고']),
                                env=dict(os.environ, HOME=str(self.home), TTS_SUMMARY='on'), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(calls.exists(), 'say 직접 호출 대신 공용 재생 worker를 사용해야 함')
        recorded = json.loads(calls.read_text())
        self.assertEqual(recorded['text'], '진행 보고')
        self.assertIn('--interim', recorded['args'])

    def test_codex_question_dispatches_provider_without_saying_descriptions(self) -> None:
        hooks = self.home / '.codex/hooks-macos'
        shutil.copytree(MACOS, hooks)
        calls = self.home / 'calls.json'
        (hooks / 'tts_playback.py').write_text(
            'import json,sys\nfrom pathlib import Path\n'
            f'Path({str(calls)!r}).write_text(json.dumps({{"text":sys.stdin.read()}}))\n')
        self.write_config(enabled='on', interim='on', provider='azure-api')
        payload = {'tool_name': 'request_user_input', 'tool_input': {'questions': [
            {'question': '선택하세요.', 'options': [{'label': '선택 A', 'description': '읽으면 안 됨'}]}]}}
        result = subprocess.run(without_live_audio(['bash', str(hooks / 'ask-question-tts.sh')]), input=json.dumps(payload),
                                env=dict(os.environ, HOME=str(self.home), TTS_SUMMARY='on'), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(calls.exists(), '질문도 공용 provider worker를 사용해야 함')
        text = json.loads(calls.read_text())['text']
        self.assertIn('선택 A', text)
        self.assertNotIn('읽으면 안 됨', text)

    def test_codex_provider_failure_does_not_fall_back_to_say(self) -> None:
        hooks = self.home / '.codex/hooks-macos'
        shutil.copytree(MACOS, hooks)
        marker = self.home / 'say-called'
        binaries = self.home / 'bin'
        binaries.mkdir()
        say = binaries / 'say'
        say.write_text(f'#!/bin/sh\ntouch "{marker}"\n')
        say.chmod(0o755)
        (hooks / 'play-tts-azure-api.sh').write_text('#!/bin/bash\nexit 1\n')
        self.write_config(enabled='on', interim='on', provider='azure-api')
        result = subprocess.run(without_live_audio(['bash', str(hooks / 'stop-tts.sh'), '--speak', '--interim']), input='진행 보고',
            env=dict(os.environ, HOME=str(self.home), TTS_SUMMARY='on', PATH=str(binaries)+os.pathsep+os.environ['PATH']),
            capture_output=True, text=True)
        self.assertFalse(marker.exists(), '설정한 API 오류를 say로 숨기면 안 됨')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.home / '.codex/TTS-Summary/txt').exists())

    def test_codex_muted_session_does_not_dispatch_interim_audio(self) -> None:
        self.write_config(enabled='on', interim='on', provider='azure-api')
        self.assertEqual(self.run_script('play-tts-briefing.sh', '보고',
            BRIEFING_TTS_DRYRUN='1', TTS_SUMMARY='off'), '')
        self.assertEqual(self.run_script('ask-question-tts.sh', stdin=json.dumps(QUESTION),
            ASK_TTS_DRYRUN='1', TTS_SUMMARY='off'), '')

    def test_selected_api_provider_receives_text_and_existing_config_unchanged(self) -> None:
        hooks = self.home / '.codex/hooks-macos'
        shutil.copytree(MACOS, hooks)
        received = self.home / 'received'
        for provider in ('azure-api', 'gemini-api', 'elevenlabs-api'):
            with self.subTest(provider=provider):
                self.write_config(enabled='on', provider=provider, voice_azure='ko-KR-YuJinNeural', speed='7.5')
                before = self.config.read_bytes()
                (hooks / f'play-tts-{provider}.sh').write_text(
                    '#!/bin/bash\nprintf "%s" "$1" > "'+str(received)+'"\n')
                result = subprocess.run(without_live_audio(['bash', str(hooks / 'stop-tts.sh'), '--speak', '--interim']),
                    input='정확한 질문 1.25입니다.', text=True, capture_output=True,
                    env=dict(os.environ, HOME=str(self.home), TTS_SUMMARY='on'))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(received.read_text(), '정확한 질문 1.25입니다.')
                self.assertEqual(self.config.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
