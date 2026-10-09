// pi에 동봉된 jiti로 확장을 로드하고 실제 셸 설정기를 사용한다. 음성 작업자만 대체한다.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, readdirSync, rmSync, realpathSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
let pkg = dirname(realpathSync(execFileSync("which", ["pi"], { encoding: "utf8" }).trim()));
while (!(() => { try { return JSON.parse(readFileSync(join(pkg, "package.json"))).name === "@earendil-works/pi-coding-agent"; } catch { return false; } })()) {
  const next = dirname(pkg);
  if (next === pkg) throw new Error("pi 1.1.0 이상을 설치하세요.");
  pkg = next;
}
const { createJiti } = createRequire(join(pkg, "package.json"))("jiti");
const jiti = createJiti(import.meta.url);

test("pi TTS 수명주기와 명령", async (t) => {
  const home = mkdtempSync(join(tmpdir(), "pi-tts-test-"));
  const agent = join(home, ".pi/agent");
  const previous = { HOME: process.env.HOME, PI_CODING_AGENT_DIR: process.env.PI_CODING_AGENT_DIR, TTS_SUMMARY: process.env.TTS_SUMMARY };
  process.env.HOME = home;
  process.env.PI_CODING_AGENT_DIR = agent;
  delete process.env.TTS_SUMMARY;
  execFileSync("python3", [join(root, "scripts/install_pi_tts.py"), "--home", home]);
  const log = join(agent, "calls.jsonl");
  writeFileSync(join(agent, "hooks/tts_playback.py"),
    "import json,sys,os\nfrom pathlib import Path\np=Path(__file__).parents[1]/'calls.jsonl'\nwith p.open('a') as f: f.write(json.dumps({'args':sys.argv[1:],'text':sys.stdin.read(),'agent':os.environ.get('AGENT_DIR_NAME')})+'\\n')\n");
  const factory = (await jiti.import(join(root, "assets/pi/tts-summary.ts"))).default;
  const make = () => {
    const events = {}, commands = {}, notices = [];
    factory({ on: (name, fn) => { events[name] = fn; }, registerCommand: (name, cmd) => { commands[name] = cmd; } });
    return { events, commands, notices, ctx: { hasUI: true, ui: { notify: (s) => notices.push(s) } } };
  };
  const configPath = join(agent, "TTS-Summary/tts-config.txt");
  const configure = (value) => writeFileSync(configPath, `enabled=${value}\nverbosity=2\nprovider=say\n`);
  const calls = () => { try { return readFileSync(log, "utf8").trim().split("\n").filter(Boolean).map(JSON.parse); } catch { return []; } };
  const start = async (h) => {
    const result = await h.events.before_agent_start({ systemPrompt: "원래 지침", prompt: "테스트" }, h.ctx);
    const match = result?.systemPrompt.match(/"([^"\n]*\/tts-summary\.txt)"/);
    return { path: match?.[1], result };
  };
  const boundary = (h, outcome = "completed", more = {}) => h.events.agent_before_settle({ outcome, entries: [], continue: false, context: { canContinue: false }, ...more }, h.ctx);
  const settle = (h, aborted = false) => h.events.agent_settled({ aborted }, h.ctx);
  try {
    await t.test("정상 완료 한 번 재생, 임시 파일 정리, 내용은 셸 코드로 실행하지 않음", async () => {
      configure("on"); const h = make(); const { path } = await start(h);
      const text = '정상 요약입니다. $(touch SHOULD_NOT_EXIST) `literal`';
      writeFileSync(path, text); await boundary(h); const before = calls().length;
      await settle(h); await settle(h);
      assert.equal(calls().length, before + 1); assert.equal(calls().at(-1).text, text);
      assert.equal(calls().at(-1).agent, ".pi/agent");
      assert.equal(readdirSync(join(agent, "TTS-Summary/pending")).length, 0);
    });
    await t.test("canContinue=false에서도 보충은 한 번, 다른 확장 entries 보존", async () => {
      const h = make(); const { path } = await start(h);
      const other = { type: "custom", customType: "other" };
      const retry = await boundary(h, "completed", { entries: [other] });
      assert.equal(retry.continue, true); assert.equal(retry.entries[0], other);
      assert.equal(await boundary(h), undefined);
      writeFileSync(path, "보충한 요약입니다."); await boundary(h); await settle(h);
      assert.equal(calls().at(-1).text, "보충한 요약입니다.");
    });
    await t.test("두 번 누락 시 경고, 재생 없음", async () => {
      const h = make(); await start(h); const before = calls().length;
      await boundary(h); await boundary(h); await settle(h);
      assert.equal(calls().length, before); assert.match(h.notices.join(""), /작성되지 않아/);
    });
    await t.test("중단과 오류에서는 기존 요약도 재생하지 않음", async () => {
      for (const outcome of ["aborted", "error"]) {
        const h = make(); const { path } = await start(h); const before = calls().length;
        writeFileSync(path, "읽히면 안 됨"); await boundary(h, outcome); await settle(h, outcome === "aborted");
        assert.equal(calls().length, before);
      }
    });
    await t.test("off와 세션 음소거에서는 요약 경로와 보충 요청 없음", async () => {
      configure("off"); let h = make(); assert.equal((await start(h)).path, undefined);
      assert.equal(await boundary(h), undefined); await settle(h);
      configure("on"); process.env.TTS_SUMMARY = "off"; h = make();
      assert.equal((await start(h)).path, undefined); delete process.env.TTS_SUMMARY;
    });
    await t.test("완료 전 off로 변경하면 재생 없음", async () => {
      const h = make(); const { path } = await start(h); const before = calls().length;
      writeFileSync(path, "읽히면 안 됨"); await boundary(h); configure("off"); await settle(h);
      assert.equal(calls().length, before); configure("on");
    });
    await t.test("서로 다른 세션의 요약 경로 격리와 종료 정리", async () => {
      const a = make(), b = make(); const first = await start(a), second = await start(b);
      assert.notEqual(first.path, second.path);
      await a.events.session_shutdown(); writeFileSync(second.path, "두 번째 세션");
      await boundary(b); await settle(b); assert.equal(calls().at(-1).text, "두 번째 세션");
    });
    await t.test("설정 명령은 모델 호출 없이 적용, pause는 공백 요약을 만들지 않음", async () => {
      const h = make(); await h.commands.tts.handler("speed 7.5", h.ctx);
      assert.match(readFileSync(configPath, "utf8"), /speed=7.5/);
      await h.commands["tts-pause"].handler("", h.ctx);
      assert.ok(calls().at(-1).args.includes("pause"));
      assert.ok(!readdirSync(agent).includes("tts-summary.txt"));
      await h.commands["tts-replay"].handler("", h.ctx);
      assert.match(h.notices.join(""), /다시 재생할 요약 음성이 없습니다/);
    });
  } finally {
    for (const [key, value] of Object.entries(previous)) { if (value === undefined) delete process.env[key]; else process.env[key] = value; }
    rmSync(home, { recursive: true, force: true });
  }
});
