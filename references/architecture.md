# Architecture

## Loop

The reusable TTS summary loop has five moving parts:

1. A global instruction file tells the agent to write the final turn briefing to a temp file.
2. The agent writes `tts-summary.txt` by file edit at the end of the turn.
3. A Stop hook runs after the turn and reads that temp file.
4. A local TTS script generates and plays audio.
5. The hook archives the summary under `TTS-Summary/txt` and the audio under `TTS-Summary/wav`, keeping only the latest 10 of each.

The agent should not call the TTS script directly. Direct playback belongs to the Stop hook so the main response flow stays predictable.

## Home Folder Boundaries

Each CLI should own its own complete loop when possible:

| Agent | Instruction file | Temp summary | Archive folders |
| --- | --- | --- | --- |
| Claude Code | `.claude/CLAUDE.md` | `.claude/tts-summary.txt` | `.claude/TTS-Summary/txt`, `.claude/TTS-Summary/wav` |
| Codex CLI | `.codex/AGENTS.md` | `.codex/tts-summary.txt` | `.codex/TTS-Summary/txt`, `.codex/TTS-Summary/wav` |
| Gemini CLI | `.gemini/GEMINI.md` | `.gemini/tts-summary.txt` | `.gemini/TTS-Summary/txt`, `.gemini/TTS-Summary/wav` |
| Antigravity CLI | usually shared `.gemini/GEMINI.md` | usually shared `.gemini/tts-summary.txt` | usually shared `.gemini/TTS-Summary/txt`, `.gemini/TTS-Summary/wav` |

Antigravity CLI may keep separate state under `.antigravitycli`, but in the observed setup its hook and global-instruction behavior was tied to Gemini-compatible configuration under `.gemini`.

## AgentVibes Provenance

This setup started from AgentVibes-inspired scripts, so old file names or environment variables may contain `agentvibes` or `AGENTVIBES`. That does not mean an AgentVibes CLI/app is still required.

When auditing a machine, distinguish between:

- Historical names: wrappers, comments, env vars, or log labels that mention AgentVibes.
- Runtime dependency: an actual executable call such as `agentvibes`, `agentvibes.exe`, or a package entry point.

If no runtime call exists, the instruction files should avoid presenting AgentVibes as a required tool.
