@echo off
:: Gemini/Antigravity용 Stop hook wrapper (Windows)
:: 목적 1) PowerShell을 숨김(-WindowStyle Hidden)으로 실행해 빈 콘솔 창이 뜨지 않게 한다.
:: 목적 2) Go 기반 훅 엔진의 quoting/escaping 문제를 단순 .cmd 경로 호출로 우회한다.
:: 목적 3) stdout에 빈 JSON {} 만 내보내 JSON stdout을 기대하는 훅 schema를 만족시킨다. 진단은 로그로 보낸다.
:: 이식 방법: 아래 .gemini 경로를 대상 에이전트 홈으로 바꾼다.
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%USERPROFILE%\.gemini\hooks\stop-tts.ps1" >> "%USERPROFILE%\.gemini\log\stop-wrapper.log" 2>&1
echo {}
