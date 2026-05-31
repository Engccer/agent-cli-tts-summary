# Troubleshooting

## No Audio Plays

Check in this order:

1. Did the agent write a non-empty `tts-summary.txt`?
2. Did the Stop hook run?
3. Did the hook read the same path the instruction file wrote?
4. Did a new TXT archive appear under `TTS-Summary/txt`?
5. Did a new WAV archive appear under `TTS-Summary/wav`?
6. Did the playback process fail silently because of a missing voice, missing API key, missing `ffmpeg`, or non-interactive prompt?

## Antigravity Needs Restart

Antigravity may cache hook settings at session start. After changing hook JSON files or wrapper commands, exit and start a fresh Antigravity CLI session before testing.

## Encoding Looks Broken

If Korean output appears as mojibake in the CLI, the hook may be emitting text in an unexpected encoding or the terminal code page may not match. Keep hook stdout minimal and write diagnostics to UTF-8 log files.

## PowerShell Command Escaping Fails

Some hook engines parse command arrays differently from an interactive shell. If direct `powershell.exe -File ...` invocation fails, use a `.cmd` wrapper with a simple path and let the wrapper call PowerShell.

## Visible Console Window Appears

Use hidden process creation for playback helpers:

- PowerShell: `-WindowStyle Hidden`
- WMI: `Win32_ProcessStartup.ShowWindow = 0`
- Avoid visible helper terminals for detached audio playback.

## Gemini API TTS Fails

If `gemini-2.5-flash-tts` returns 404 with an API-key `generateContent` path, verify the current API availability for that key and endpoint. In the observed setup, `gemini-3.1-flash-tts-preview` worked through the local Converters script.

Also ensure non-interactive TTS scripts do not call `input()` unguarded. EOF prompts can make hooks appear to fail after audio generation.

## AgentVibes Mentions

AgentVibes mentions in script names or environment variables are historical unless an actual AgentVibes executable is called. Do not add AgentVibes to global user instructions as a dependency unless the local runtime truly invokes it.
