@echo off
:: Stop hook wrapper (Antigravity CLI, cmd registration path).
:: Runs stop-tts-wrapper.ps1 and forwards its JSON stdout to the CLI; stderr goes to a log.
:: Port note: change the .gemini path below to the target agent home.
if not exist "%USERPROFILE%\.gemini\log" mkdir "%USERPROFILE%\.gemini\log"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.gemini\hooks\stop-tts-wrapper.ps1" 2>> "%USERPROFILE%\.gemini\log\stop-wrapper-cmd.log"
