#!/usr/bin/env python3
"""계획 모드 Stop의 현재 턴 final 앞부분을 한 번만 선택한다."""

import argparse
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


def claim(agent_dir: Path, session: str, turn: str) -> bool:
    directory = agent_dir / 'TTS-Summary/final-fallback'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f'{session}.json').open('a+', encoding='utf-8') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        saved = stream.read()
        turns = json.loads(saved) if saved else []
        if not isinstance(turns, list) or any(not isinstance(x, str) for x in turns):
            raise ValueError('발췌 재생 기록을 확인할 수 없습니다.')
        if turn in turns:
            return False
        turns.append(turn)
        stream.seek(0)
        stream.truncate()
        json.dump(turns, stream)
        stream.flush()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError('Stop 입력이 객체가 아닙니다.')
        session, turn, text = select(args.agent_dir, payload)
        if claim(args.agent_dir, session, turn):
            print(text, end='')
    except (OSError, ValueError, TypeError) as error:
        print(f'현재 턴 발췌 생략: {error}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
