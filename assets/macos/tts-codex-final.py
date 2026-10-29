#!/usr/bin/env python3
"""Codex Stop의 요약·공백 억제·현재 턴 발췌를 같은 잠금 안에서 한 번만 소비한다."""

import argparse
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import re
import sys

from tts_transcripts import _codex_turns, _read_markers, _validate_id


def excerpt(text: str) -> str:
    # 뒤쪽 본문을 대신 고르면 더 이상 '응답 앞부분'이 아니다.
    first = text.strip().split('\n\n', 1)[0]
    if not first or re.match(r'^(?:```|~~~|\||[-*+]\s|\d+[.)]\s)', first):
        raise ValueError('응답 앞부분을 안전한 문장으로 확인할 수 없습니다.')
    first = re.sub(r'^#{1,6}\s+', '', first)
    first = re.sub(r'\[([^\]\n]+)\]\([^\n)]+\)', r'\1', first)
    first = first.replace('**', '').replace('__', '')
    first = ' '.join(first.split())
    sentences = re.split(r'(?<=[.!?。！？])\s+', first)
    selected = ' '.join(sentences[:2])
    if not selected or len(selected) > 800 or '`' in selected or '<' in selected:
        raise ValueError('응답 앞부분을 안전한 문장으로 확인할 수 없습니다.')
    return '응답 앞부분입니다. ' + selected


def select(agent_dir: Path, payload: dict) -> tuple[str, str, str]:
    if (payload.get('hook_event_name') != 'Stop' or payload.get('permission_mode') != 'plan'
            or payload.get('stop_hook_active') is not False):
        raise ValueError('계획 모드의 최초 Stop을 확인할 수 없습니다.')
    session, turn = payload.get('session_id'), payload.get('turn_id')
    _validate_id(session)
    _validate_id(turn)
    path = payload.get('transcript_path')
    if not isinstance(path, str):
        raise ValueError('현재 대화 기록 경로가 없습니다.')
    expected = list((agent_dir / 'sessions').glob(f'**/rollout-*-{session}.jsonl'))
    if len(expected) != 1 or Path(path).resolve(strict=True) != expected[0].resolve(strict=True):
        raise ValueError('현재 대화 기록 경로가 일치하지 않습니다.')
    turns = _codex_turns(agent_dir, session)
    if (not turns or turns[-1]['id'] != turn or turns[-1]['control']
            or turn in _read_markers(agent_dir, 'codex', session)):
        raise ValueError('현재 대화 턴을 확인할 수 없습니다.')
    answer = payload.get('last_assistant_message')
    if not isinstance(answer, str) or not answer.strip() or turns[-1]['answers'] != [answer]:
        raise ValueError('현재 턴 final과 Stop 본문이 일치하지 않습니다.')
    return session, turn, excerpt(answer)


@contextmanager
def turn_record(agent_dir: Path, session: str):
    directory = agent_dir / 'TTS-Summary/final-fallback'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f'{session}.json').open('a+', encoding='utf-8') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        saved = stream.read()
        turns = json.loads(saved) if saved else []
        if not isinstance(turns, list) or any(not isinstance(x, str) for x in turns):
            raise ValueError('Stop 처리 기록을 확인할 수 없습니다.')
        yield stream, turns


def consume_stop(agent_dir: Path, payload: dict) -> str:
    summary = agent_dir / 'tts-summary.txt'
    session, turn = payload.get('session_id'), payload.get('turn_id')
    try:
        if payload.get('hook_event_name') != 'Stop':
            raise ValueError('Stop 식별자가 없습니다.')
        _validate_id(session)
        _validate_id(turn)
    except ValueError:
        # 옛 payload의 파일 소비는 유지한다. 식별자 없이 final을 발췌하지 않는다.
        if not summary.is_file():
            raise ValueError('현재 Stop 세션·턴을 확인할 수 없습니다.')
        text = summary.read_text(encoding='utf-8')
        summary.unlink()
        return text

    with turn_record(agent_dir, session) as (stream, turns):
        if turn in turns:
            return ''
        has_summary = summary.is_file()
        if has_summary:
            text = summary.read_text(encoding='utf-8')
        else:
            _, _, text = select(agent_dir, payload)
        # 파일 삭제와 stdout 전달 전에 처리권을 기록한다. 공백도 처리 완료다.
        turns.append(turn)
        stream.seek(0)
        stream.truncate()
        json.dump(turns, stream)
        stream.flush()
        if has_summary:
            summary.unlink()
        return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError('Stop 입력이 객체가 아닙니다.')
        print(consume_stop(args.agent_dir, payload), end='')
    except (OSError, ValueError, TypeError) as error:
        print(f'Codex Stop 처리 생략: {error}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
