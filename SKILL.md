---
name: agent-cli-tts-summary
description: "Claude Code, Codex CLI, Gemini CLI, Antigravity CLI 같은 로컬 코딩 에이전트 CLI에 TTS 턴 요약 기능(요약 언어 선택 가능, 기본 한국어)을 설치, 점검, 이식, 복구할 때 사용한다. 새 컴퓨터 셋업, 훅 기반 TTS 요약 루프 마이그레이션, 각 에이전트 폴더 안에서 루프가 완결되는지 검증, 음성 재생 실패 디버깅, OS 내장 음성 대신 고품질 Gemini API·ElevenLabs API 음성으로 전환(tts-provider.txt), 요약 누락 방지 가드나 질문 선택지 음성 안내 같은 보조 훅 추가, 훅/스크립트/글로벌 지침 관계 정리에 적합하다."
---

# Agent CLI TTS Summary

## 개요

이 스킬은 코딩 에이전트 CLI의 응답 요약을 음성으로 듣기 위한 훅 기반 TTS 루프를 재사용 가능한 형태로 정리한다. 에이전트가 턴 종료 시 `tts-summary.txt`에 요약을 쓰고, Stop hook이 그 파일을 읽어 음성을 생성·재생한 뒤 TXT와 WAV 보관본을 각 에이전트 홈 폴더 아래에 정리한다. 요약 언어는 설치 시 선택할 수 있고 기본값은 한국어다.

핵심 설계 원칙은 에이전트별 내부 완결성이다. Claude, Codex, Gemini/Antigravity가 서로의 스크립트나 보관 폴더를 침범하지 않도록 `.claude`, `.codex`, `.gemini` 안에 가능한 한 완결된 루프를 둔다. 이 루프는 외부 TTS CLI나 앱에 런타임 의존하지 않으며, 기본 재생은 OS 내장 기능(Windows SAPI, macOS `say`)만 쓴다. 고품질 음성을 원하면 세 CLI 어디서나 동일하게 에이전트 홈의 `tts-provider.txt`로 Gemini API 또는 ElevenLabs API provider로 전환할 수 있고(유료 API 키 필요), API provider가 실패하면 OS 내장 음성으로 자동 폴백한다.

## 이식성 / 외부 의존

다른 컴퓨터에서 이 스킬을 그대로 수행하기 전에 무엇이 자체 완결적이고 무엇을 함께 챙겨야 하는지 먼저 파악한다.

- **자체 완결(추가 설치 없이 동작)**: OS 내장 음성 기반 기본 루프. `assets/windows/stop-tts.ps1` + `assets/windows/play-tts-windows-sapi.ps1`은 Windows 내장 `System.Speech`만 쓰고 외부 스크립트를 참조하지 않는다. macOS `assets/macos/stop-tts.sh`는 내장 `say`/`afconvert`/`afplay`만 쓴다. 경로는 모두 현재 사용자 홈(`$env:USERPROFILE`/`$HOME`)에서 동적으로 잡는다. 두 `scripts/*.py`도 표준 라이브러리만 쓴다.
- **외부 의존(함께 가져와야 동작)**: 고품질 API provider 2종은 speech-toolkit( https://github.com/Engccer/speech-toolkit )의 TTS 스크립트를 호출한다. Gemini provider(`play-tts-gemini-api.ps1`/`.sh`)는 speech-toolkit + `GEMINI_API_KEY` + (속도 보정 시) `ffmpeg`, ElevenLabs provider(`play-tts-elevenlabs-api.ps1`/`.sh`)는 speech-toolkit + `ELEVENLABS_API_KEY`가 필요하며 Windows 판은 MP3를 WAV로 바꾸기 위해 `ffmpeg`가 필수다(macOS는 `afplay`가 MP3를 재생하므로 선택). 둘 다 유료 API이고, 없거나 실패하면 OS 내장 provider로 폴백하므로 핵심 기능은 막히지 않는다. 각 스크립트 상단 `$ConverterScript`/`CONVERTER_SCRIPT` 경로를 새 환경에 맞게 바꾼다.
- **반드시 치환할 값**: `assets/hooks/*.json`의 `<USER_HOME>`은 실제 홈 경로로 바꿔야 한다. `inspect_tts_loop.py`로 실제 홈과 폴더 구조를 먼저 확인한 뒤 치환한다. 그대로 붙여넣지 않는다.
- **인코딩 주의**: `assets/windows/*.ps1`은 한글 주석 때문에 UTF-8 with BOM으로 저장돼 있다. 복사·수정 시 BOM을 보존해야 한다. BOM이 빠지면 Windows PowerShell 5.1이 파일을 ANSI로 읽어, 한글로 끝나는 줄이 다음 줄을 삼키는 파싱 오류가 생길 수 있다(`references/troubleshooting.md` 참고).
- **전제 런타임(스킬 밖이지만 필요)**: Windows는 PowerShell + 최소 1개의 SAPI 음성(기본 음성으로 충족, NaturalVoice는 선택), macOS는 `say`. 모두 OS 기본 제공이다.

## 작업 흐름

1. 기존 에이전트 홈 폴더를 먼저 점검한다.
   - `scripts/inspect_tts_loop.py --root <사용자-홈>`으로 글로벌 지침, 훅 설정, 훅 스크립트, 음성/속도 파일, 보관 폴더를 확인한다.
   - Claude, Codex, Gemini/Antigravity가 각각 `.claude`, `.codex`, `.gemini` 안에서 자체 스크립트와 보관 폴더를 쓰는지 확인한다.

2. 요약 언어와 재생 provider를 사용자와 확인한다.
   - **요약 언어**: 기본값은 한국어다. 사용자가 다른 언어를 원하는지 한 번 확인하고, 특별한 선택이 없으면 한국어로 진행한다. 선택한 언어는 4단계의 지침 블록(`--language`)과 provider별 음성·언어 설정(SAPI/`say` 음성 이름, `tts-language-code.txt`, ElevenLabs 음성)에 함께 반영한다.
   - **재생 provider**: 기본값은 OS 내장 음성(Windows SAPI, macOS `say`)이며 무료·오프라인이다. 사용자가 고품질 음성을 원하면 Gemini API 또는 ElevenLabs API를 선택할 수 있다(세 CLI 공통, 유료 API 키 필요). 선택 결과는 에이전트 홈의 `tts-provider.txt`에 적는다: Windows `windows-sapi`(기본)/`gemini-api`/`elevenlabs-api`, macOS `say`(기본)/`gemini-api`/`elevenlabs-api`. 파일이 없으면 OS 내장 음성을 쓴다.

3. 플랫폼별 구현 방식을 선택한다.
   - Windows: PowerShell 훅을 기본으로 사용한다. 세 CLI 모두 SAPI/NaturalVoice 음성을 기본으로 쓰고, `tts-provider.txt`로 Gemini API 또는 ElevenLabs API TTS로 전환할 수 있다(실패 시 SAPI 폴백). 자세한 내용은 `references/windows.md`를 본다.
   - macOS: shell hook과 `say` 음성을 기본으로 사용한다. `tts-provider.txt`로 Gemini API 또는 ElevenLabs API TTS로 전환할 수 있다(실패 시 `say` 폴백). 필요하면 `afplay`나 `ffmpeg` 후처리를 함께 쓴다. 자세한 내용은 `references/macos.md`를 본다.

4. 스크립트를 설치한다.
   - 처음부터 작성하지 말고 `assets/`의 검증된 템플릿을 복사해 경로만 치환한다. 각 파일 상단의 `$AgentDirName`(Windows) 또는 `AGENT_DIR_NAME`(macOS) 한 줄만 대상 에이전트 폴더명으로 바꾸면 된다(복사한 모든 파일에서 같은 값으로).
   - Windows: `assets/windows/stop-tts.ps1` + `play-tts-windows-sapi.ps1`을 대상 홈의 `hooks-windows`(Gemini는 `hooks`)에 둔다. API provider를 쓰면 `play-tts-gemini-api.ps1`/`play-tts-elevenlabs-api.ps1`도 같은 폴더에 두고 `$ConverterScript`를 치환한다. Gemini/Antigravity는 `stop-tts-wrapper.ps1`(+`.cmd` 등록 경로면 `stop-tts-wrapper.cmd`)도 함께 둔다. `.ps1`은 UTF-8 with BOM을 보존해 복사한다.
   - macOS: `assets/macos/stop-tts.sh`를 대상 홈의 훅 폴더에 둔다. API provider를 쓰면 `play-tts-gemini-api.sh`/`play-tts-elevenlabs-api.sh`도 같은 폴더에 두고 `CONVERTER_SCRIPT`를 치환한다.
   - 설치 순서와 주의(비밀값 금지 등)는 `assets/README.md`를 본다.

5. 글로벌 지침을 갱신한다.
   - `scripts/render_instruction_block.py`로 에이전트·플랫폼·요약 언어에 맞는 표준 TTS 지침 블록을 생성한다(`--language`, 기본 한국어).
   - 생성한 블록을 `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` 상단 가까이에 넣는다.
   - 지침의 임시 요약 파일 경로와 보관 폴더 경로가 실제 훅 스크립트의 경로와 일치해야 한다.

6. Stop hook을 등록한다.
   - `assets/hooks/`의 설정 샘플(`claude.settings.json` / `codex.hooks.json` / `gemini.settings.json`)을 환경에 맞게 경로 치환해 각 에이전트 설정에 병합한다.
   - 훅은 에이전트가 작성한 임시 `tts-summary.txt`를 읽고, 같은 홈 아래 `TTS-Summary/txt`·`TTS-Summary/wav`에 보관하며 각각 최신 10개만 남긴다.
   - 템플릿은 실패 시 CLI 턴을 깨지 않도록 조용히 종료하고, 필요하면 fallback 알림음을 낸다.

7. 끝까지 검증한다.
   - 짧은 에이전트 응답을 한 번 발생시킨다.
   - 임시 요약 파일이 생성되고 훅에 의해 처리되는지 확인한다.
   - `TTS-Summary/txt`와 `TTS-Summary/wav`에 새 보관본이 생기는지 확인한다.
   - Windows에서는 음성 재생 때 별도 콘솔 창이 뜨지 않는지도 확인한다.

## 선택 훅

기본 요약 루프 위에 필요하면 다음 보조 훅을 더한다. 둘 다 기본 루프와 같은 음성/속도 파일을 재사용하며, 없어도 요약 재생 자체는 동작한다.

- **요약 누락 가드 (Stop hook 내장)**: 에이전트가 `tts-summary.txt`를 쓰지 않고 턴을 끝내면, 아직 한 번도 재요청하지 않은 경우에 한해 Stop hook이 `exit 2`로 응답을 차단하고 요약 작성을 요구한다. Stop hook payload(stdin)의 `stop_hook_active`가 true면 이미 한 번 재요청한 것이므로 무한루프를 피해 통과한다. `assets/macos/stop-tts.sh`와 `assets/windows/stop-tts.ps1`에 들어 있다. 이 가드가 발동하려면 훅 명령이 payload를 stdin으로 받을 수 있어야 한다.
- **질문 선택지 음성 안내 (PreToolUse hook)**: `AskUserQuestion` 도구 호출 직전, 질문 본문과 선택지 라벨을 한국어로 조립해 음성으로 읽어 준다(선택지 설명은 스크린리더 TUI 탐색과 중복되므로 생략). 도구 호출을 절대 차단하지 않고 백그라운드로 재생한다. macOS 검증본은 `assets/macos/ask-question-tts.sh`다. Windows 대응본은 아직 없다.

## 참고 문서

- `references/architecture.md`: 공통 루프 구조, 에이전트별 경로, 외부 의존성 원칙.
- `references/windows.md`: Windows 훅, 음성/provider 파일, 숨김 재생, Gemini API TTS 구성.
- `references/macos.md`: macOS `say` 기반 구성과 음성 선택 예시.
- `references/instruction-blocks.md`: 글로벌 지침에 넣을 표준 TTS 요약 규칙.
- `references/troubleshooting.md`: 구현 과정에서 확인한 실패 유형과 해결책.

## 스크립트

- `scripts/inspect_tts_loop.py`: 로컬 에이전트 TTS 폴더 구조를 진단한다.
- `scripts/render_instruction_block.py`: 대상 에이전트·플랫폼·요약 언어에 맞는 글로벌 지침 블록을 출력한다(`--language`, 기본 한국어. 그 외 언어는 영어 블록에 해당 언어를 지정).

## 자산

검증된 훅·재생 스크립트와 훅 설정 샘플을 `assets/`에 둔다. 설치 시 처음부터 작성하지 말고 복사해 경로만 치환한다. 파일 지도와 설치 순서는 `assets/README.md` 참고.

- `assets/windows/`: Windows용 `stop-tts.ps1`, provider 3종(SAPI/Gemini API/ElevenLabs API), Gemini/Antigravity용 wrapper 2종(`stop-tts-wrapper.ps1`: 합성 전용 실행 + WAV 숨김 분리 재생 + JSON stdout, `stop-tts-wrapper.cmd`: `.cmd` 등록 경로용).
- `assets/macos/`: macOS `stop-tts.sh`(기본 `say`), provider 2종(Gemini API/ElevenLabs API), 질문 선택지 음성 안내 `ask-question-tts.sh`.
- `assets/hooks/`: Claude·Codex·Gemini 훅 등록 샘플(비밀값 미포함).

## 에이전트 인터페이스 메타

`agents/openai.yaml`은 Codex/OpenAI 계열 에이전트가 이 스킬을 노출할 때 쓰는 표시 이름·기본 프롬프트 정의다. Claude Code 동작에는 영향이 없으며, 멀티 에이전트 호환을 위한 부가 메타데이터다.

## 관련 프로젝트

시각장애 사용자를 위한 에이전트 스킬 번들 [skills-for-the-blind](https://github.com/Engccer/skills-for-the-blind)의 멤버 스킬이다.
