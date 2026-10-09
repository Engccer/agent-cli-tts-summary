import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { homedir } from "node:os";
import { join, relative, resolve } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

// pi 1.1.0의 최종 완료 이벤트를 사용한다. 공용 재생기는 stdin으로 요약을 받는다.
export default function (pi: ExtensionAPI) {
  const home = homedir();
  const agentDir = resolve((process.env.PI_CODING_AGENT_DIR || join(home, ".pi/agent"))
    .replace(/^~(?=\/|$)/, home));
  const hooks = join(agentDir, "hooks");
  const env = { ...process.env, AGENT_DIR_NAME: relative(home, agentDir) };
  type Pending = { dir: string; file: string; retried: boolean; completed: boolean };
  let pending: Pending | undefined;

  function run(command: string, args: string[], input = "", extraEnv = {}) {
    return new Promise<string>((accept, reject) => {
      const child = spawn(command, args, { env: { ...env, ...extraEnv }, stdio: "pipe" });
      let stdout = "", stderr = "";
      const timer = setTimeout(() => child.kill("SIGTERM"), 15000);
      child.stdout.setEncoding("utf8").on("data", (data) => { stdout += data; });
      child.stderr.setEncoding("utf8").on("data", (data) => { stderr += data; });
      child.on("error", (error) => { clearTimeout(timer); reject(error); });
      child.stdin.on("error", () => {}); // 일찍 종료한 자식의 EPIPE는 close에서 처리한다.
      child.on("close", (code) => {
        clearTimeout(timer);
        if (code === 0) accept(stdout.trim());
        else reject(new Error(stderr.trim() || `TTS 명령 실패 (${code})`));
      });
      child.stdin.end(input);
    });
  }

  function report(ctx: ExtensionContext, message: string, error = false) {
    if (ctx.hasUI) ctx.ui.notify(message, error ? "warning" : "info");
    else console.error(message);
  }

  async function config() {
    const message = await run("/bin/bash", [join(hooks, "tts-config-context.sh")]);
    return { message, enabled: message.includes("요약 켬") };
  }

  async function summary(turn: Pending) {
    try {
      const info = await stat(turn.file);
      if (!info.isFile() || info.size > 65536) return "";
      return (await readFile(turn.file, "utf8")).trim();
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return "";
      throw error;
    }
  }

  async function cleanup() {
    const previous = pending;
    pending = undefined;
    if (previous) await rm(previous.dir, { recursive: true, force: true });
  }

  pi.on("before_agent_start", async (event, ctx) => {
    await cleanup();
    try {
      const setting = await config();
      if (!setting.enabled) return {
        systemPrompt: `${event.systemPrompt}\n\n이번 요청은 TTS 음성 요약 끔. 음성 요약 파일을 작성하지 않는다.`,
      };
      const parent = join(agentDir, "TTS-Summary/pending");
      await mkdir(parent, { recursive: true, mode: 0o700 });
      const dir = await mkdtemp(join(parent, "turn-"));
      pending = { dir, file: join(dir, "tts-summary.txt"), retried: false, completed: false };
      return { systemPrompt: `${event.systemPrompt}\n\n${setting.message}\n` +
        `최종 답변 전에 이번 요청의 한국어 음성 요약을 파일 작성 도구로 ${JSON.stringify(pending.file)}에 저장한다. ` +
        "위 상세 정도의 문장 수를 따른다. 요약 자체가 사용자에게 보내는 답변이다. " +
        "질문에 답할 때는 정답과 핵심 근거를 직접 말한다. 작업을 수행했을 때는 실제 변경 결과와 남은 문제를 말한다. " +
        "모든 문장에 사용자가 알아야 할 사실이나 행동을 담는다. " +
        "요청 분석, 설명 방식, 답변 작성 과정, '설명했다/정리했다/준비했다'는 자기 보고는 쓰지 않는다. 오류는 실제로 있었을 때만 넣는다. " +
        "요약을 먼저 저장하고 사용자에게 본문 답변을 보낸다. 음성 재생은 확장이 하므로 직접 실행하지 않는다. " +
        "이 요청의 요약 경로는 위 경로 하나다. 다른 에이전트의 tts-summary.txt에는 쓰지 않는다." };
    } catch (error) {
      await cleanup();
      report(ctx, `TTS 준비 실패: ${String(error)}`, true);
    }
  });

  pi.on("agent_before_settle", async (event, ctx) => {
    const turn = pending;
    if (!turn) return;
    turn.completed = event.outcome === "completed";
    if (!turn.completed || event.continue || turn.retried) return;
    try {
      if (!(await config()).enabled || await summary(turn)) return;
      turn.retried = true;
      turn.completed = false;
      // custom_message를 추가하면 pi가 canContinue를 다시 계산한다.
      return { entries: [...event.entries, {
        type: "custom_message" as const, customType: "tts-summary-retry", display: false,
        content: `음성 요약이 누락되었습니다. 이번 응답의 한국어 요약을 ${JSON.stringify(turn.file)}에 파일 작성 도구로 저장하세요. 본문 답변을 반복하지 마세요.`,
      }], continue: true };
    } catch (error) {
      report(ctx, `TTS 요약 확인 실패: ${String(error)}`, true);
    }
  });

  pi.on("agent_start", () => { if (pending) pending.completed = false; });

  pi.on("agent_settled", async (event, ctx) => {
    const turn = pending;
    pending = undefined; // 중복 이벤트가 와도 한 번만 처리한다.
    if (!turn) return;
    try {
      if (event.aborted || !turn.completed || !(await config()).enabled) return;
      const text = await summary(turn);
      if (!text) { report(ctx, "음성 요약이 작성되지 않아 이번 낭독을 건너뜁니다.", true); return; }
      await run("python3", [join(hooks, "tts_playback.py"), "run", "--launchd",
        "--agent-dir", agentDir, "--", "/bin/bash", join(hooks, "stop-tts.sh"), "--speak"], text);
    } catch (error) {
      report(ctx, `TTS 재생 시작 실패: ${String(error)}`, true);
    } finally {
      await rm(turn.dir, { recursive: true, force: true });
    }
  });

  pi.on("session_shutdown", cleanup);

  for (const [name, script, description] of [
    ["tts", "tts-config-set.sh", "음성 요약 설정: on/off, speed 1~10, verbosity 1~3"],
    ["tts-replay", "tts-replay.sh", "직전 음성 요약 다시 듣기"],
    ["tts-pause", "tts-pause.sh", "pi의 현재 음성 낭독 중지"],
  ]) {
    pi.registerCommand(name, { description, handler: async (args, ctx) => {
      try {
        // pi 명령은 모델을 호출하지 않으므로 공용 스크립트의 공백 요약 파일도 불필요하다.
        const extra = name === "tts" ? {} : { TTS_SUMMARY: "off" };
        report(ctx, await run("/bin/bash", [join(hooks, script), args], "", extra));
      } catch (error) { report(ctx, String(error), true); }
    } });
  }
}
