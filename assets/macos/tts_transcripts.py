"""Codex와 agy의 현재 세션에서 완료 응답 원문만 선택한다.

컨트롤 실행자는 read/replay/pause 실행 전에 mark_control_turn을 호출한다.
자연어 호출도 그 턴을 제외할 수 있도록 TTS-Summary/control-turns/<id>.json에
턴 ID(Codex) 또는 USER_INPUT의 step_index(agy)만 저장한다. 본문은 저장하지 않는다.
"""

import fcntl
import json
from pathlib import Path
import re
import sys


def _validate_id(session_id: str) -> None:
    if not isinstance(session_id, str) or not re.fullmatch(r"[a-zA-Z0-9-]+", session_id):
        raise ValueError("현재 세션 ID를 확인할 수 없습니다.")


def is_control_command(text: str) -> bool:
    """명시적 명령만 인식한다. 자연어 의도는 실행자가 턴 표시로 전달한다."""
    command = r"(?:tts[- ](?:read|replay|pause)|codex-tts[- ](?:read|replay|pause))"
    return bool(re.fullmatch(rf"\s*[/$]{command}\s*", text)
                or re.search(rf"<command-name>[/$]{command}</command-name>", text)
                or re.fullmatch(rf"\s*\[\${command}\]\([^\n]+\)\s*", text)
                or re.search(rf"<skill>\s*<name>{command}</name>", text)
                or re.search(rf"<skill-name>{command}</skill-name>", text))


def _rows(path: Path) -> list[dict]:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ValueError("현재 세션의 대화 기록을 읽을 수 없습니다.") from error
    rows = []
    lines = data.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (ValueError, UnicodeDecodeError) as error:
            # append 중인 마지막 행만 허용한다. 중간 손상은 턴 경계를 잃게 한다.
            if index == len(lines) - 1 and not line.endswith(b"\n"):
                break
            raise ValueError("대화 기록이 손상되어 응답을 선택할 수 없습니다.") from error
        if not isinstance(row, dict):
            raise ValueError("대화 기록 형식을 확인할 수 없습니다.")
        rows.append(row)
    return rows


def _codex_turns(agent_dir: Path, session_id: str) -> list[dict]:
    _validate_id(session_id)
    paths = list((agent_dir / "sessions").glob(f"**/rollout-*-{session_id}.jsonl"))
    if len(paths) != 1:
        raise ValueError("현재 세션의 대화 기록을 하나로 확인할 수 없습니다.")
    rows = _rows(paths[0])
    metas = [row.get("payload") for row in rows if row.get("type") == "session_meta"]
    if len(metas) != 1 or not isinstance(metas[0], dict) or metas[0].get("id") != session_id:
        raise ValueError("대화 기록의 세션 ID가 일치하지 않습니다.")
    turns = []
    current = None
    for row in rows:
        kind, payload = row.get("type"), row.get("payload", {})
        if not isinstance(payload, dict):
            raise ValueError("대화 기록 형식을 확인할 수 없습니다.")
        event = payload.get("type") if kind == "event_msg" else None
        if event == "thread_rolled_back":
            count = payload.get("num_turns")
            if type(count) is not int or count < 0:
                raise ValueError("되감기 기록을 확인할 수 없습니다.")
            while count and turns:
                removed = turns.pop()
                if removed["user"]:
                    count -= 1
            current = None
            continue
        if event == "task_started" or kind == "turn_context":
            turn_id = payload.get("turn_id")
            if not isinstance(turn_id, str) or not turn_id:
                raise ValueError("대화 턴 ID를 확인할 수 없습니다.")
            if current is None or current["id"] != turn_id:
                if any(turn["id"] == turn_id for turn in turns):
                    raise ValueError("대화 턴 경계가 중복되어 응답을 선택할 수 없습니다.")
                current = {"id": turn_id, "user": False, "control": False,
                           "answers": [], "completed_answer": None, "done": False}
                turns.append(current)
            elif event == "task_started":
                current["done"] = False
            continue
        if event == "task_complete":
            if current is not None and payload.get("turn_id") == current["id"]:
                current["done"] = True
                if current["answers"]:
                    current["completed_answer"] = current["answers"][-1]
            continue
        if kind != "response_item" or payload.get("type") != "message" or current is None:
            continue
        content = payload.get("content", [])
        if not isinstance(content, list):
            continue
        if payload.get("role") == "user":
            current["user"] = True
            text = "\n".join(block["text"] for block in content
                             if isinstance(block, dict) and block.get("type") == "input_text"
                             and isinstance(block.get("text"), str))
            current["control"] |= is_control_command(text)
        elif payload.get("role") == "assistant" and payload.get("phase") == "final_answer":
            text = "".join(block["text"] for block in content
                           if isinstance(block, dict) and block.get("type") == "output_text"
                           and isinstance(block.get("text"), str))
            if text.strip():
                # 완료 뒤 추가된 본문에 이전 완료 증거를 재사용하지 않는다.
                current["done"] = False
                current["answers"] = [text]
    return turns


def _agy_turns(agent_dir: Path, session_id: str) -> list[dict]:
    _validate_id(session_id)
    path = (agent_dir / "antigravity-cli" / "brain" / session_id
            / ".system_generated" / "logs" / "transcript_full.jsonl")
    rows = _rows(path)
    turns = []
    current = None
    previous_index = -1
    for row in rows:
        index = row.get("step_index")
        if type(index) is not int or index <= previous_index:
            raise ValueError("대화 단계 순서를 하나로 확인할 수 없습니다.")
        previous_index = index
        if row.get("type") == "USER_INPUT":
            current = {"id": index, "control": is_control_command(row.get("content", ""))
                       if isinstance(row.get("content"), str) else False,
                       "answers": [], "done": False}
            turns.append(current)
        elif current is not None and row.get("source") == "MODEL" and row.get("type") == "PLANNER_RESPONSE":
            current["done"] = False
            if (row.get("status") == "DONE" and not row.get("tool_calls")
                    and isinstance(row.get("content"), str) and row["content"].strip()):
                current["answers"] = [row["content"]]
                current["done"] = True
    return turns


def _marker_path(agent_dir: Path, session_id: str) -> Path:
    _validate_id(session_id)
    return agent_dir / "TTS-Summary" / "control-turns" / f"{session_id}.json"


def _markers(data: str, agent: str, session_id: str) -> set:
    if not data:
        return set()
    try:
        value = json.loads(data)
        ids = value["turn_ids"]
        if (value.get("agent") != agent or value.get("session_id") != session_id
                or not isinstance(ids, list)
                or any((not isinstance(x, str) or not x) if agent == "codex"
                       else (type(x) is not int or x < 0) for x in ids)):
            raise ValueError
        return set(ids)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ValueError("낭독 제어 턴 기록을 확인할 수 없습니다.") from error


def _read_markers(agent_dir: Path, agent: str, session_id: str) -> set:
    path = _marker_path(agent_dir, session_id)
    try:
        with path.open(encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            return _markers(stream.read(), agent, session_id)
    except FileNotFoundError:
        return set()


def mark_control_turn(agent_dir: Path, agent: str, session_id: str) -> None:
    """현재 미완료 턴을 표시한다. 완료 후 셸에서 실행하면 정상 응답은 유지한다."""
    if agent not in {"codex", "agy"}:
        raise ValueError("지원하지 않는 대화 기록입니다.")
    turns = (_codex_turns if agent == "codex" else _agy_turns)(agent_dir, session_id)
    if not turns or turns[-1]["done"]:
        return
    path = _marker_path(agent_dir, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        ids = _markers(stream.read(), agent, session_id)
        ids.add(turns[-1]["id"])
        stream.seek(0)
        stream.truncate()
        json.dump({"agent": agent, "session_id": session_id, "turn_ids": sorted(ids)}, stream)
        stream.write("\n")


def _last(turns: list[dict], excluded: set) -> str:
    for turn in reversed(turns):
        if turn["control"] or turn["id"] in excluded:
            continue
        # 같은 Codex 턴의 Stop hook 재개는 마지막 완료 당시의 본문 하나만 읽는다.
        if "completed_answer" in turn:
            if turn["completed_answer"] is not None:
                return turn["completed_answer"]
        elif turn["done"] and turn["answers"]:
            return turn["answers"][0]
    raise ValueError("읽을 수 있는 완료 응답이 없습니다.")


def last_codex_response(agent_dir: Path, session_id: str) -> str:
    return _last(_codex_turns(agent_dir, session_id), _read_markers(agent_dir, "codex", session_id))


def last_agy_response(agent_dir: Path, session_id: str) -> str:
    return _last(_agy_turns(agent_dir, session_id), _read_markers(agent_dir, "agy", session_id))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["mark"])
    parser.add_argument("--agent", choices=["codex", "agy"], required=True)
    parser.add_argument("--agent-dir", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    try:
        mark_control_turn(args.agent_dir, args.agent, args.session_id)
    except (OSError, ValueError) as error:
        print(f"낭독 제어 턴을 기록하지 못했습니다: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
