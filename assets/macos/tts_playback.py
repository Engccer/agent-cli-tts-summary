#!/usr/bin/env python3
"""에이전트별 TTS 작업 등록과 중지. 등록된 고유 작업의 프로세스 그룹만 종료한다.

--queue로 시작한 작업은 사용자 단위 재생 잠금을 쥔 동안에만 명령을 실행한다. 세 CLI의 모든 세션이
같은 잠금을 쓰므로 소리를 내는 작업은 한 번에 하나만 돌고, 나머지는 작업자 안에서 차례를 기다린다.
"""

import argparse
import base64
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import uuid


@contextmanager
def registry(agent_dir):
    directory = Path(agent_dir) / "TTS-Summary/playback"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / "jobs.json"
        try:
            jobs = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            jobs = {}
        try:
            yield jobs
        finally:
            temporary = directory / "jobs.tmp"
            temporary.write_text(json.dumps(jobs))
            os.replace(temporary, path)


def is_worker(pid, token):
    try:
        if os.getpgid(pid) != pid:
            return False
        result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="],
                                capture_output=True, text=True, check=False)
        return result.returncode == 0 and "tts_playback.py worker" in result.stdout and token in result.stdout
    except ProcessLookupError:
        return False


def request_path(agent_dir, token):
    return Path(agent_dir) / "TTS-Summary/playback" / f"{token}.json"


def launchd_label(token):
    return f"space.dodoplanet.tts.{token}"


QUEUE_WAIT_SECONDS = 600  # 차례를 기다리는 최대 시간. TTS_PLAYBACK_QUEUE_WAIT(초)로 바꿀 수 있다.


def queue_lock_path(environment):
    """재생 잠금 파일. TTS_PLAYBACK_LOCK으로 바꿀 수 있고, 기본은 에이전트와 무관한 사용자 캐시 폴더다."""
    custom = environment.get("TTS_PLAYBACK_LOCK")
    if custom:
        return Path(custom)
    home = environment.get("HOME")
    return (Path(home) if home else Path.home()) / "Library/Caches/agent-cli-tts-summary/playback.lock"


@contextmanager
def playback_turn(queue, environment):
    """queue면 앞선 재생이 끝날 때까지 기다린다. 잠금을 쥔 작업자가 죽으면 커널이 잠금을 푼다."""
    if not queue:
        yield
        return
    # 잠금을 열 수 없거나 차례가 제한 시간 안에 오지 않으면 기다리지 않고 재생한다.
    # 요약이 들리지 않는 것보다 겹치는 편이 낫고, 멈춘 작업 하나가 모든 CLI의 음성을 막아서는 안 된다.
    lock = None
    try:
        wait = int(environment.get("TTS_PLAYBACK_QUEUE_WAIT") or QUEUE_WAIT_SECONDS)
    except ValueError:
        wait = QUEUE_WAIT_SECONDS
    try:
        path = queue_lock_path(environment)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = path.open("a")

        def expired(signum, frame):
            raise TimeoutError(f"{wait}초 동안 차례가 오지 않음")
        previous = signal.signal(signal.SIGALRM, expired)
        signal.alarm(max(wait, 1))
        try:
            # 기다리는 중에 SIGTERM(pause)이 오면 신호 처리기가 대기를 끊고 작업자를 끝낸다.
            fcntl.flock(lock, fcntl.LOCK_EX)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
    except OSError as error:
        print(f"TTS 재생 대기열을 기다리지 않고 재생: {error}", file=sys.stderr, flush=True)
    try:
        yield
    finally:
        if lock:
            lock.close()


def start(command, agent_dir, background=False, stdin=None, launchd=False, queue=False):
    token = uuid.uuid4().hex
    options = ["--queue"] if queue else []
    args = [sys.executable, str(Path(__file__).resolve()), "worker",
            "--agent-dir", str(agent_dir), "--token", token, *options, "--", *command]
    log_dir = Path(agent_dir) / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    with registry(agent_dir) as jobs, (log_dir / "tts-playback.log").open("ab") as log:
        if launchd:
            # Stop hook의 자손 정리와 무관한 일회성 launchd 작업. 비밀 환경값은
            # 사용자 전용 요청 파일로 전달하고 작업자가 읽자마자 지운다.
            request = request_path(agent_dir, token)
            data = (stdin or sys.stdin.buffer).read()
            with open(request, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
                json.dump({"command": command, "environment": dict(os.environ),
                           "stdin": base64.b64encode(data).decode()}, stream)
            jobs[token] = {"pid": 0, "launchd": True}
            args = [sys.executable, str(Path(__file__).resolve()), "worker", "--agent-dir", str(agent_dir),
                    "--token", token, "--launchd", *options]
            result = subprocess.run(["/bin/launchctl", "submit", "-l", launchd_label(token),
                                     "-o", str(log_dir / "tts-playback.log"),
                                     "-e", str(log_dir / "tts-playback.log"), "--", *args],
                                    capture_output=True, text=True)
            if result.returncode:
                request.unlink(missing_ok=True)
                jobs.pop(token, None)
                raise RuntimeError(f"TTS 작업 시작 실패: {result.stderr.strip()}")
            return 0
        # lock을 해제하기 전에는 작업자가 명령을 실행할 수 없다.
        process = subprocess.Popen(args, stdin=stdin, stdout=log if background else None,
                                   stderr=log if background else None, start_new_session=True)
        jobs[token] = {"pid": process.pid, "launchd": False}
    if background:
        try:
            return process.wait(timeout=0.15)
        except subprocess.TimeoutExpired:
            threading.Thread(target=process.wait, daemon=True).start()
            return 0
    result = process.wait()
    return 0 if result < 0 else result


def pause(agent_dir):
    stopped = 0
    with registry(agent_dir) as jobs:
        for token, job in list(jobs.items()):
            if not isinstance(job, dict) or not isinstance(token, str) or len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
                jobs.pop(token, None)
                continue
            pid = job.get("pid")
            if isinstance(pid, int) and is_worker(pid, token):
                try:
                    os.killpg(pid, signal.SIGTERM)
                    stopped += 1
                except ProcessLookupError:
                    pass
            if job.get("launchd"):
                result = subprocess.run(["/bin/launchctl", "remove", launchd_label(token)],
                                        capture_output=True, check=False)
                if pid == 0 and result.returncode == 0:
                    stopped += 1
            request_path(agent_dir, token).unlink(missing_ok=True)
            jobs.pop(token, None)
    return stopped


def worker(command, agent_dir, token, launchd=False, queue=False):
    with registry(agent_dir) as jobs:
        job = jobs.get(token)
        if not job or job.get("pid") not in (0, os.getpid()):
            return 0  # 시작 직후 pause가 먼저 실행된 작업은 재생하지 않는다.
        job["pid"] = os.getpid()
    def interrupted(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        if launchd:
            request = request_path(agent_dir, token)
            try:
                data = json.loads(request.read_text())
            except FileNotFoundError:
                return 0  # pause가 시작 요청까지 먼저 정리했다.
            finally:
                request.unlink(missing_ok=True)
            environment = dict(data["environment"], TTS_PLAYBACK_MANAGED="1")
            with tempfile.TemporaryFile() as source, playback_turn(queue, environment):
                source.write(base64.b64decode(data["stdin"]))
                source.seek(0)
                return subprocess.run(data["command"], stdin=source, env=environment, check=False).returncode
        with playback_turn(queue, os.environ):
            return subprocess.run(command, env=dict(os.environ, TTS_PLAYBACK_MANAGED="1"), check=False).returncode
    finally:
        with registry(agent_dir) as jobs:
            jobs.pop(token, None)
        if launchd:
            # submit으로 만든 일회성 job을 남기지 않는다. 이 호출이 자신도 종료한다.
            subprocess.run(["/bin/launchctl", "remove", launchd_label(token)], capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "worker", "pause"))
    parser.add_argument("--agent-dir", type=Path, required=True)
    parser.add_argument("--token", default="")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--launchd", action="store_true")
    parser.add_argument("--queue", action="store_true", help="사용자 단위 재생 잠금으로 순서대로 실행")
    arguments = sys.argv[1:]
    boundary = arguments.index("--") if "--" in arguments else len(arguments)
    args = parser.parse_args(arguments[:boundary])
    command = arguments[boundary + 1:]
    if args.action == "pause":
        count = pause(args.agent_dir)
        print("현재 낭독을 중지했습니다." if count else "현재 낭독 중인 작업이 없습니다.")
        return 0
    if not command and not (args.action == "worker" and args.launchd):
        parser.error("실행할 TTS 명령이 필요합니다.")
    if args.action == "worker":
        return worker(command, args.agent_dir, args.token, args.launchd, args.queue)
    return start(command, args.agent_dir, args.background, launchd=args.launchd, queue=args.queue)


if __name__ == "__main__":
    sys.exit(main())
