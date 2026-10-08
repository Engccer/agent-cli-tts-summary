#!/usr/bin/env python3
"""Claude, Codex, agy의 macOS 전문 낭독. Markdown 파서와 내장 음성을 사용한다."""

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile


def find_transcript(agent_dir: Path, session_id: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9-]+", session_id):
        raise ValueError("현재 세션 ID를 확인할 수 없습니다.")
    # cwd는 /cd와 worktree 이동으로 바뀔 수 있어 세션 ID로만 찾는다.
    matches = list((agent_dir / "projects").glob(f"*/{session_id}.jsonl"))
    if len(matches) != 1:
        raise ValueError("현재 세션의 대화 기록을 하나로 확인할 수 없습니다.")
    return matches[0]


def text_blocks(message: dict) -> list[str]:
    content = message.get("content", [])
    if isinstance(content, str):
        return [content]
    return [b["text"] for b in content if isinstance(b, dict)
            and b.get("type") == "text" and isinstance(b.get("text"), str)]


def is_read_command(text: str) -> bool:
    return bool(re.search(r"<command-name>/(?:tts-read|tts-replay|tts-pause)</command-name>", text)
                or re.fullmatch(r"\s*/(?:tts-read|tts-replay|tts-pause)\s*", text))


def last_response(path: Path) -> str:
    records = {}
    leaf = None
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # 실행 중 마지막 행이 아직 기록 중일 수 있다.
            if not isinstance(row, dict) or row.get("isSidechain") or not row.get("uuid"):
                continue
            records[row["uuid"]] = row
            leaf = row["uuid"]

    # 되감기로 버린 응답은 읽지 않고 현재 대화 가지의 parentUuid를 따라간다.
    chain = []
    seen = set()
    while leaf in records and leaf not in seen:
        seen.add(leaf)
        row = records[leaf]
        chain.append(row)
        leaf = row.get("parentUuid")
    chain.reverse()

    skip_turn = False
    groups = {}
    latest = None
    for row in chain:
        message = row.get("message", {})
        if not isinstance(message, dict):
            continue
        if row.get("type") == "user" and not row.get("isMeta"):
            texts = text_blocks(message)
            if texts:
                skip_turn = is_read_command("\n".join(texts))
        if row.get("type") != "assistant" or skip_turn or row.get("isApiErrorMessage"):
            continue
        # thinking/tool_use(요약 Write 포함)/tool_result는 텍스트 후보에 들어가지 않는다.
        key = message.get("id") or row["uuid"]
        groups.setdefault(key, []).extend(text_blocks(message))
        if message.get("stop_reason") == "end_turn" and groups[key]:
            latest = key
    if latest is None:
        raise ValueError("읽을 수 있는 완료 응답이 없습니다.")
    return "\n\n".join(groups[latest])


def speech_text(text: str) -> str:
    """CommonMark의 코드 블록 위치만 치환하고 나머지는 원문 그대로 둔다."""
    from markdown_it import MarkdownIt

    # 파서의 행 번호는 CR/CRLF를 LF로 정규화한 결과다. 원래 줄 끝은 보존한다.
    lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", text)
    output = []
    cursor = 0
    for token in MarkdownIt("commonmark").parse(text):
        if token.type not in {"fence", "code_block"} or token.map is None:
            continue
        start, end = token.map
        output.extend(lines[cursor:start])
        info = token.info.strip().split()
        language = info[0].strip("{}.") if info else ""
        language = language if re.fullmatch(r"[\w#+.-]{1,40}", language) else ""
        output.append(f"{language + ' ' if language else ''}코드 블록입니다.\n")
        cursor = end
    output.extend(lines[cursor:])
    return "".join(output)


def speak(text: str, voice: str, rate: int, agent_dir: Path) -> None:
    from tts_playback import start
    args = [sys.executable, str(Path(__file__).resolve()), "--speak", "--rate", str(rate),
            "--voice", voice, "--agent-dir", str(agent_dir)]
    # 작업자에게 파일 디스크립터로 넘겨 argv 길이 제한을 피한다.
    with tempfile.TemporaryFile() as source:
        source.write(text.encode("utf-8"))
        source.seek(0)
        result = start(args, agent_dir, background=True, stdin=source)
        if result:
            raise ValueError(f"음성 재생에 실패했습니다. {agent_dir}/log/tts-playback.log를 확인하세요.")


def play_stdin(voice: str, rate: int) -> int:
    def interrupted(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, interrupted)
    # say는 /dev/stdin을 거부한다. 전용 작업자가 파일 수명을 재생 종료까지 관리한다.
    with tempfile.NamedTemporaryFile(prefix="tts-read-", suffix=".txt") as source:
        import shutil
        shutil.copyfileobj(sys.stdin.buffer, source)
        source.flush()
        args = ["/usr/bin/say", "-r", str(rate), "-f", source.name]
        if voice:
            args.extend(["-v", voice])
        return subprocess.run(args, check=False).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-dir", type=Path, required=True)
    parser.add_argument("--agent", choices=("claude", "codex", "agy"), default="claude")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--speak", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--voice", default="")
    parser.add_argument("--rate", type=int, default=200)
    args = parser.parse_args()
    if args.speak:
        sys.exit(play_stdin(args.voice, args.rate))
    try:
        if args.agent == "claude":
            original = last_response(find_transcript(args.agent_dir, args.session_id))
        else:
            from tts_transcripts import last_codex_response, last_agy_response, mark_control_turn
            mark_control_turn(args.agent_dir, args.agent, args.session_id)
            reader = last_codex_response if args.agent == "codex" else last_agy_response
            original = reader(args.agent_dir, args.session_id)
        text = speech_text(original)
        if os.environ.get("TTS_READ_DRYRUN") == "1":
            print(json.dumps({"voice": args.voice, "rate": args.rate, "text": text}, ensure_ascii=False))
            return
        speak(text, args.voice, args.rate, args.agent_dir)
        print("마지막 응답 전문을 읽습니다. 코드 블록은 종류만 안내합니다.")
    except ModuleNotFoundError:
        print("전문 낭독에 markdown-it-py가 필요합니다. 설치 안내를 확인하세요.")
    except (OSError, ValueError) as error:
        print(f"전문 낭독을 시작하지 못했습니다: {error}")


if __name__ == "__main__":
    main()
