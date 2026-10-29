"""현재 턴만 발췌하고 누락 가드·중복 재생을 만들지 않는 Codex Stop 계약."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CodexFinalFallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.agent = self.home / '.codex'
        self.hooks = self.agent / 'hooks-macos'
        shutil.copytree(ROOT / 'assets/macos', self.hooks)
        config = self.agent / 'TTS-Summary'
        config.mkdir()
        (config / 'tts-config.txt').write_text('enabled=on\nprovider=azure-api\n')
        self.calls = self.home / 'calls.jsonl'
        (self.hooks / 'tts_playback.py').write_text(
            'import json,sys,os\nfrom pathlib import Path\n'
            'with Path(os.environ["CALLS"]).open("a") as f:\n'
            ' f.write(json.dumps({"args":sys.argv[1:],"text":sys.stdin.read()})+"\\n")\n')
        sessions = self.agent / 'sessions'
        sessions.mkdir()
        self.transcript = sessions / 'rollout-test-session.jsonl'
        self.rows = [{'type': 'session_meta', 'payload': {'id': 'session'}}]
        self.answer('old', '이전 턴 응답입니다.', complete=True)
        self.answer('current', '현재 첫 문장입니다. 현재 두 번째 문장입니다. 세 번째는 읽지 않습니다.')
        self.payload = {'hook_event_name': 'Stop', 'session_id': 'session', 'turn_id': 'current',
                        'transcript_path': str(self.transcript), 'permission_mode': 'plan',
                        'stop_hook_active': False,
                        'last_assistant_message': '현재 첫 문장입니다. 현재 두 번째 문장입니다. 세 번째는 읽지 않습니다.'}

    def answer(self, turn, text, *, complete=False, phase='final_answer'):
        self.rows += [
            {'type': 'turn_context', 'payload': {'turn_id': turn}},
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                'content': [{'type': 'input_text', 'text': '질문'}]}},
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'phase': phase,
                'content': [{'type': 'output_text', 'text': text}]}},
        ]
        if complete:
            self.rows.append({'type': 'event_msg', 'payload': {'type': 'task_complete', 'turn_id': turn}})

    def run_hook(self, payload=None, **env):
        self.transcript.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in self.rows))
        result = subprocess.run(['bash', str(self.hooks / 'stop-tts.sh')],
            input=json.dumps(self.payload if payload is None else payload), capture_output=True, text=True,
            env=dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME='.codex', TTS_SUMMARY='on',
                     CALLS=str(self.calls)) | env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_plan_reads_current_final_without_task_complete_and_only_once(self):
        calls = self.run_hook()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['text'], '응답 앞부분입니다. 현재 첫 문장입니다. 현재 두 번째 문장입니다.')
        self.assertEqual(len(self.run_hook()), 1)
        self.assertFalse((self.agent / 'tts-summary.txt').exists())

    def test_identity_phase_and_payload_mismatch_never_read_previous_answer(self):
        for change in [{'turn_id': 'old'}, {'session_id': 'other'}, {'transcript_path': '/tmp/other'},
                       {'last_assistant_message': '이전 턴 응답입니다.'}, {'last_assistant_message': None},
                       {'turn_id': ''}, {'hook_event_name': 'SubagentStop'}, {'permission_mode': 'default'},
                       {'stop_hook_active': True}]:
            with self.subTest(change=change):
                self.assertEqual(self.run_hook(self.payload | change), [])

    def test_commentary_or_new_turn_cannot_reuse_old_final(self):
        self.rows[-1]['payload']['phase'] = 'commentary'
        self.assertEqual(self.run_hook(), [])
        self.rows[-1]['payload']['phase'] = 'final_answer'
        self.rows.append({'type': 'turn_context', 'payload': {'turn_id': 'newer'}})
        self.assertEqual(self.run_hook(), [])

    def test_missing_identity_does_not_request_another_model_turn(self):
        self.assertEqual(self.run_hook({}), [])

    def test_blank_summary_suppresses_fallback(self):
        (self.agent / 'tts-summary.txt').write_text('\n')
        self.assertEqual(self.run_hook(), [])

    def test_normal_summary_then_repeated_plan_stop_does_not_read_fallback(self):
        (self.agent / 'tts-summary.txt').write_text('정상 요약입니다.')
        self.assertEqual([c['text'] for c in self.run_hook()], ['정상 요약입니다.'])
        self.assertEqual([c['text'] for c in self.run_hook()], ['정상 요약입니다.'])

    def test_blank_suppression_then_repeated_plan_stop_stays_silent(self):
        (self.agent / 'tts-summary.txt').write_text('\n')
        self.assertEqual(self.run_hook(), [])
        self.assertEqual(self.run_hook(), [])

    def test_muted_or_disabled_preserves_silence(self):
        # 세션 음소거는 실제 공유 파일에 대응하는 임시 파일도 보존해야 한다.
        summary = self.agent / 'tts-summary.txt'
        summary.write_text('다른 세션 요약')
        self.assertEqual(self.run_hook(TTS_SUMMARY='off'), [])
        self.assertEqual(summary.read_text(), '다른 세션 요약')
        summary.unlink()
        (self.agent / 'TTS-Summary/tts-config.txt').write_text('enabled=off\n')
        self.assertEqual(self.run_hook(), [])

    def test_unsafe_markdown_prefix_is_not_replaced_with_later_prose(self):
        text = '```python\nprint(1)\n```\n뒤의 설명입니다.'
        self.rows[-1]['payload']['content'][0]['text'] = text
        self.assertEqual(self.run_hook(self.payload | {'last_assistant_message': text}), [])

    def test_first_sentence_preserves_decimal_and_stops_at_paragraph(self):
        text = '가격은 1.25달러입니다.\n\n다음 단락은 읽지 않습니다.'
        self.rows[-1]['payload']['content'][0]['text'] = text
        self.assertEqual(self.run_hook(self.payload | {'last_assistant_message': text})[0]['text'],
                         '응답 앞부분입니다. 가격은 1.25달러입니다.')

    def test_control_turn_never_falls_back(self):
        self.rows[-2]['payload']['content'][0]['text'] = '$codex-tts-read'
        self.assertEqual(self.run_hook(), [])

    def test_fallback_does_not_require_interim_enabled(self):
        (self.agent / 'TTS-Summary/tts-config.txt').write_text('enabled=on\ninterim=off\n')
        self.assertEqual(len(self.run_hook()), 1)

    def test_installer_supplies_executable_fallback_dependencies_and_preserves_config(self):
        from install_macos_commands import install
        config = self.agent / 'TTS-Summary/tts-config.txt'
        before = config.read_bytes()
        # 실제 배포 파일 목록만으로 현재 턴 선택과 재생 전달이 가능해야 한다.
        shutil.rmtree(self.hooks)
        install(self.home, 'codex', update_stop_hook=True)
        for name in ('tts-codex-final.py', 'ask-question-tts.sh', 'play-tts-briefing.sh'):
            self.assertTrue((self.hooks / name).is_file())
        (self.hooks / 'tts_playback.py').write_text(
            'import json,sys,os\nfrom pathlib import Path\n'
            'with Path(os.environ["CALLS"]).open("a") as f:\n'
            ' f.write(json.dumps({"args":sys.argv[1:],"text":sys.stdin.read()})+"\\n")\n')
        self.assertEqual(len(self.run_hook()), 1)
        self.assertEqual(config.read_bytes(), before)

    def simultaneous_callbacks(self):
        self.transcript.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in self.rows))
        env = dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME='.codex', TTS_SUMMARY='on', CALLS=str(self.calls))
        processes = [subprocess.Popen(['bash', str(self.hooks / 'stop-tts.sh')], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env) for _ in range(2)]
        for process in processes:
            process.stdin.write(json.dumps(self.payload))
            process.stdin.close()
            process.stdin = None
        for process in processes:
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_simultaneous_stop_callbacks_dispatch_current_turn_once(self):
        self.assertEqual(len(self.simultaneous_callbacks()), 1)

    def test_simultaneous_normal_summary_callbacks_never_dispatch_fallback(self):
        (self.agent / 'tts-summary.txt').write_text('정상 요약입니다.')
        self.assertEqual([c['text'] for c in self.simultaneous_callbacks()], ['정상 요약입니다.'])
        self.assertEqual([c['text'] for c in self.run_hook()], ['정상 요약입니다.'])

    def test_simultaneous_blank_suppression_callbacks_stay_silent(self):
        (self.agent / 'tts-summary.txt').write_text('\n')
        self.assertEqual(self.simultaneous_callbacks(), [])
        self.assertEqual(self.run_hook(), [])

    def test_normal_summary_without_hook_identity_keeps_legacy_consumption(self):
        (self.agent / 'tts-summary.txt').write_text('payload 없는 정상 요약입니다.')
        self.assertEqual([c['text'] for c in self.run_hook({})], ['payload 없는 정상 요약입니다.'])
        self.assertFalse((self.agent / 'tts-summary.txt').exists())

    def test_speak_interim_without_payload_does_not_consume_summary_or_claim_turn(self):
        summary = self.agent / 'tts-summary.txt'
        summary.write_text('다음 정상 요약')
        received = self.home / 'provider-text'
        (self.hooks / 'play-tts-azure-api.sh').write_text(
            '#!/bin/bash\nprintf "%s" "$1" > "'+str(received)+'"\n')
        result = subprocess.run(['bash', str(self.hooks / 'stop-tts.sh'), '--speak', '--interim'],
            input='payload 없는 중간보고', capture_output=True, text=True,
            env=dict(os.environ, HOME=str(self.home), AGENT_DIR_NAME='.codex', TTS_SUMMARY='on'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(received.read_text(), 'payload 없는 중간보고')
        self.assertEqual(summary.read_text(), '다음 정상 요약')
        self.assertFalse((self.agent / 'TTS-Summary/final-fallback').exists())


if __name__ == '__main__':
    unittest.main()
