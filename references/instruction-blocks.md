# Instruction Blocks

Use the same summary style rules across Claude, Codex, Gemini, and Antigravity so the spoken result feels consistent.

Generate a path-specific block with:

```bash
python scripts/render_instruction_block.py --agent codex --platform windows --home C:/Users/pc/.codex
```

## Canonical Style Rules

- TTS summary text is written in Korean.
- Avoid self-quotation and meta narration. Do not say "the user asked" or "I explained".
- Write like a final spoken briefing the user can hear directly.
- For simple code edits, use 2-3 sentences.
- For medium implementation work, use 4-6 sentences.
- For complex architecture changes or debugging, use 7-10 sentences.
- For non-development research, writing, or briefing work, scale the summary by information volume, not by changed file count.
- Include errors or incomplete verification when they occurred.
- Do not directly invoke TTS playback from the instruction file; the Stop hook owns playback.

## Path Accuracy

The instruction block must name the actual temp file and archive folders. If the hook archives to `TTS-Summary/txt`, do not leave an older path such as a flat `tts-summary.txt` archive in global instructions.
