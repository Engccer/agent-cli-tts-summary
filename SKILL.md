---
name: agent-cli-tts-summary
description: Use this skill to install, inspect, or repair hook-based Korean TTS turn summaries for local agent CLIs such as Claude Code, Codex CLI, Gemini CLI, and Antigravity CLI. Use when setting up a new computer, migrating the TTS summary loop, checking whether each agent is self-contained, fixing missing audio playback, or documenting the hook/script/instruction relationship.
---

# Agent CLI TTS Summary

## Overview

This skill packages a reusable setup pattern for agent CLI TTS summaries: the agent writes a short Korean turn summary to `tts-summary.txt`, a Stop hook reads it, TTS audio is generated and played, then TXT and WAV artifacts are archived under that agent's own home folder.

The design goal is an internal loop per agent home folder. Historical script names may mention AgentVibes, but the current pattern does not require an AgentVibes CLI/app runtime unless the local installation explicitly calls one.

## Workflow

1. Inspect the existing agent home folders before editing.
   - Use `scripts/inspect_tts_loop.py --root <user-home>` to find instructions, hook configs, scripts, voice/rate files, archive folders, and AgentVibes references.
   - Check whether Claude, Codex, and Gemini/Antigravity each keep their own scripts and archives under `.claude`, `.codex`, and `.gemini`.

2. Choose the platform pattern.
   - Windows: use PowerShell hooks, SAPI/NaturalVoice voices for Claude/Codex, and Gemini API TTS or SAPI fallback for Gemini/Antigravity. See `references/windows.md`.
   - macOS: use shell hooks and `say` voices with optional `afplay`/`ffmpeg` post-processing. See `references/macos.md`.

3. Update global instructions.
   - Use `scripts/render_instruction_block.py` to generate the standardized Korean TTS instruction block for each agent.
   - Insert the block near the top of `CLAUDE.md`, `AGENTS.md`, or `GEMINI.md`.
   - Keep the instruction path aligned with the actual temp summary path and archive folders.

4. Wire the Stop hook.
   - The hook should read the temp `tts-summary.txt` created by the agent.
   - It should create `TTS-Summary/txt` and `TTS-Summary/wav` under the same agent home.
   - It should keep the newest 10 TXT files and newest 10 WAV files.
   - It should fail softly: log the error and optionally play a fallback sound, without breaking the CLI turn.

5. Verify end to end.
   - Trigger a short agent response.
   - Confirm the temp summary was consumed or archived as expected.
   - Confirm a new TXT archive and WAV archive exist.
   - Confirm audio playback happens without visible console windows on Windows.

## References

- `references/architecture.md`: shared loop architecture and path map.
- `references/windows.md`: Windows setup notes, voice/provider files, hidden playback, Gemini API TTS.
- `references/macos.md`: macOS `say` setup notes and known voice choices.
- `references/instruction-blocks.md`: canonical global instruction wording.
- `references/troubleshooting.md`: failure modes and fixes learned during implementation.

## Scripts

- `scripts/inspect_tts_loop.py`: local diagnostic report for agent TTS folders.
- `scripts/render_instruction_block.py`: emits a standard Korean instruction block for a target agent/platform.
