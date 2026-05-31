# macOS Setup Notes

## Recommended Layout

Use shell hooks inside each agent home folder:

- Claude: `.claude/hooks`
- Codex: `.codex/hooks-macos`
- Gemini/Antigravity: `.gemini/hooks`

Each hook should read that agent's own `tts-summary.txt` and write archives under that same home.

## Voices

The simple and portable macOS provider is `say`.

Observed working choices on a macOS setup:

- Claude Korean: `Jian (Premium)`
- Codex Korean: `Minsu (Enhanced)`
- Gemini/Antigravity Korean: `Yuna (Premium)`
- Common fast rate: around `400` words per minute

Available voice names vary by macOS install and downloaded voices. Always verify with:

```bash
say -v '?'
```

## Audio Files

Use `say -o` to generate an audio file, then convert to WAV if the local workflow expects WAV archives. If a speed change is needed beyond `say` rate, apply `ffmpeg` post-processing.

## Cleanup Rule

The macOS cleanup rule should match Windows:

- Archive TXT in `TTS-Summary/txt`.
- Archive WAV in `TTS-Summary/wav`.
- Keep the newest 10 of each.
