---
name: agent-cli-tts-summary
description: "Claude Code, Codex CLI, Gemini CLI, Antigravity CLI 같은 로컬 코딩 에이전트 CLI에 한국어 TTS 턴 요약 기능을 설치, 점검, 이식, 복구할 때 사용한다. 새 컴퓨터 셋업, 훅 기반 TTS 요약 루프 마이그레이션, 각 에이전트 폴더 안에서 루프가 완결되는지 검증, 음성 재생 실패 디버깅, 훅/스크립트/글로벌 지침 관계 정리에 적합하다."
---

# Agent CLI TTS Summary

## 개요

이 스킬은 코딩 에이전트 CLI의 응답 요약을 한국어 음성으로 듣기 위한 훅 기반 TTS 루프를 재사용 가능한 형태로 정리한다. 에이전트가 턴 종료 시 `tts-summary.txt`에 요약을 쓰고, Stop hook이 그 파일을 읽어 음성을 생성·재생한 뒤 TXT와 WAV 보관본을 각 에이전트 홈 폴더 아래에 정리한다.

핵심 설계 원칙은 에이전트별 내부 완결성이다. Claude, Codex, Gemini/Antigravity가 서로의 스크립트나 보관 폴더를 침범하지 않도록 `.claude`, `.codex`, `.gemini` 안에 가능한 한 완결된 루프를 둔다. 과거 파일명이나 변수명에 AgentVibes가 남아 있을 수 있지만, 현재 패턴은 로컬 설치가 명시적으로 호출하지 않는 한 AgentVibes CLI나 앱을 런타임 의존성으로 요구하지 않는다.

## 작업 흐름

1. 기존 에이전트 홈 폴더를 먼저 점검한다.
   - `scripts/inspect_tts_loop.py --root <사용자-홈>`으로 글로벌 지침, 훅 설정, 훅 스크립트, 음성/속도 파일, 보관 폴더, AgentVibes 언급 여부를 확인한다.
   - Claude, Codex, Gemini/Antigravity가 각각 `.claude`, `.codex`, `.gemini` 안에서 자체 스크립트와 보관 폴더를 쓰는지 확인한다.

2. 플랫폼별 구현 방식을 선택한다.
   - Windows: PowerShell 훅을 기본으로 사용한다. Claude/Codex는 SAPI/NaturalVoice 음성을 쓸 수 있고, Gemini/Antigravity는 Gemini API TTS 또는 SAPI fallback을 사용할 수 있다. 자세한 내용은 `references/windows.md`를 본다.
   - macOS: shell hook과 `say` 음성을 기본으로 사용한다. 필요하면 `afplay`나 `ffmpeg` 후처리를 함께 쓴다. 자세한 내용은 `references/macos.md`를 본다.

3. 글로벌 지침을 갱신한다.
   - `scripts/render_instruction_block.py`로 에이전트와 플랫폼에 맞는 표준 한국어 TTS 지침 블록을 생성한다.
   - 생성한 블록을 `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` 상단 가까이에 넣는다.
   - 지침의 임시 요약 파일 경로와 보관 폴더 경로가 실제 훅 스크립트의 경로와 일치해야 한다.

4. Stop hook을 연결한다.
   - 훅은 에이전트가 작성한 임시 `tts-summary.txt`를 읽는다.
   - 같은 에이전트 홈 아래에 `TTS-Summary/txt`와 `TTS-Summary/wav`를 만든다.
   - TXT와 WAV를 각각 최신 10개만 남긴다.
   - 실패 시 CLI 턴을 깨지 않도록 로그를 남기고 부드럽게 종료한다. 필요하면 fallback 알림음이나 fallback TTS를 사용한다.

5. 끝까지 검증한다.
   - 짧은 에이전트 응답을 한 번 발생시킨다.
   - 임시 요약 파일이 생성되고 훅에 의해 처리되는지 확인한다.
   - `TTS-Summary/txt`와 `TTS-Summary/wav`에 새 보관본이 생기는지 확인한다.
   - Windows에서는 음성 재생 때 별도 콘솔 창이 뜨지 않는지도 확인한다.

## 참고 문서

- `references/architecture.md`: 공통 루프 구조, 에이전트별 경로, AgentVibes 관련 정리.
- `references/windows.md`: Windows 훅, 음성/provider 파일, 숨김 재생, Gemini API TTS 구성.
- `references/macos.md`: macOS `say` 기반 구성과 음성 선택 예시.
- `references/instruction-blocks.md`: 글로벌 지침에 넣을 표준 TTS 요약 규칙.
- `references/troubleshooting.md`: 구현 과정에서 확인한 실패 유형과 해결책.

## 스크립트

- `scripts/inspect_tts_loop.py`: 로컬 에이전트 TTS 폴더 구조를 진단한다.
- `scripts/render_instruction_block.py`: 대상 에이전트와 플랫폼에 맞는 한국어 글로벌 지침 블록을 출력한다.
