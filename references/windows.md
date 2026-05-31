# Windows Setup Notes

## Recommended Layout

Use one script set per agent home:

- Claude: `.claude/hooks-windows`
- Codex: `.codex/hooks-windows`
- Gemini/Antigravity: `.gemini/hooks`

The Stop hook should read the temp summary from the same home folder and archive outputs under that same home folder.

## Voice Providers

Claude and Codex can use Windows SAPI through NaturalVoice SAPI Adapter:

- Provider file: `tts-provider.txt`
- Korean voice file: `tts-voice-sapi-ko.txt`
- English voice file: `tts-voice-sapi-en.txt`
- Rate file: `tts-speech-rate.txt`

Gemini/Antigravity can use Gemini API TTS for a more distinct voice. In the working Windows setup:

- Primary provider: Gemini API TTS
- Script: `Converters/TTS/gemini_tts.py`
- Model that worked with the local API key path: `gemini-3.1-flash-tts-preview`
- Voice: `Puck`
- Speedup: `tts-speech-rate.txt` mapped to `ffmpeg atempo`, for example `7` -> `1.7`
- Fallback: Windows SAPI voice such as `Microsoft Heami Desktop`

## Hook Invocation

Prefer simple wrapper commands that the CLI hook engine can execute reliably.

For Gemini/Antigravity, keep stdout JSON-compatible when the hook schema expects JSON output. Send diagnostics to log files or stderr if needed.

When a Go-based hook engine has trouble executing PowerShell directly, use a `.cmd` wrapper that calls PowerShell with explicit arguments.

## Hidden Playback

If Antigravity opens a visible console window for TTS playback, detach the playback through Windows process APIs:

- Start PowerShell with `-WindowStyle Hidden`.
- Use WMI `Win32_ProcessStartup.ShowWindow = 0` when launching from a wrapper.
- Avoid `Start-Process` without `-WindowStyle Hidden` for helper playback processes.

The goal is that the CLI turn completes normally and audio plays without an extra terminal window.

## Cleanup Rule

After each successful hook run:

- Save a timestamped TXT file under `TTS-Summary/txt`.
- Save a timestamped WAV file under `TTS-Summary/wav`.
- Delete older files so only the latest 10 TXT and latest 10 WAV files remain.
