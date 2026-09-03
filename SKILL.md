---
name: agent-cli-tts-summary
description: "Claude Code, Codex CLI, Gemini CLI, Antigravity CLI 같은 로컬 코딩 에이전트 CLI에 TTS 턴 요약 기능(요약 언어 선택 가능, 기본 한국어)을 설치, 점검, 이식, 복구할 때 사용한다. 새 컴퓨터 셋업, 훅 기반 TTS 요약 루프 마이그레이션, 각 에이전트 폴더 안에서 루프가 완결되는지 검증, 음성 재생 실패 디버깅, 음성 요약 켜고 끄기·속도·상세 정도·프로바이더·음성을 한 설정 파일(tts-config.txt)로 관리, OS 내장 음성 대신 고품질 Gemini API·ElevenLabs API 음성으로 전환, 요약 누락 방지 가드나 질문 선택지 음성 안내 같은 보조 훅 추가, 훅/스크립트/글로벌 지침 관계 정리에 적합하다."
metadata:
  version: "1.7.0"
---

# Agent CLI TTS Summary

## 개요

이 스킬은 코딩 에이전트 CLI의 응답 요약을 음성으로 듣기 위한 훅 기반 TTS 루프를 재사용 가능한 형태로 정리한다. 에이전트가 턴 종료 시 `tts-summary.txt`에 요약을 쓰고, Stop hook이 그 파일을 읽어 음성을 생성·재생한 뒤 TXT와 WAV 보관본을 각 에이전트 홈 폴더 아래에 정리한다. 요약 언어는 설치 시 선택할 수 있고 기본값은 한국어다.

사용 여부·속도·상세 정도·프로바이더·음성은 에이전트 홈의 `TTS-Summary/tts-config.txt` 한 파일이 정본이며, 훅과 재생 스크립트가 모두 이 파일을 읽는다.

핵심 설계 원칙은 에이전트별 내부 완결성이다. Claude, Codex, Gemini/Antigravity가 서로의 스크립트나 보관 폴더를 침범하지 않도록 `.claude`, `.codex`, `.gemini` 안에 가능한 한 완결된 루프를 둔다. 이 루프는 외부 TTS CLI나 앱에 런타임 의존하지 않으며, 기본 재생은 OS 내장 기능(Windows SAPI, macOS `say`)만 쓴다. 고품질 음성을 원하면 세 CLI 어디서나 동일하게 설정 파일의 `provider`로 Gemini API 또는 ElevenLabs API provider로 전환할 수 있고(유료 API 키 필요), API provider가 실패하면 OS 내장 음성으로 자동 폴백한다.

## 이식성 / 외부 의존

새 컴퓨터에서 이 스킬을 그대로 수행하기 전에 무엇이 자체 완결적이고 무엇을 함께 챙겨야 하는지 먼저 파악한다.

- **자체 완결(추가 설치 없이 동작)**: OS 내장 음성 기반 기본 루프. `assets/windows/stop-tts.ps1` + `assets/windows/play-tts-windows-sapi.ps1`은 Windows 내장 `System.Speech`만 쓰고 외부 스크립트를 참조하지 않는다. macOS `assets/macos/stop-tts.sh`는 내장 `say`/`afconvert`/`afplay`만 쓴다. 경로는 모두 현재 사용자 홈(`$env:USERPROFILE`/`$HOME`)에서 동적으로 잡는다. 두 `scripts/*.py`도 표준 라이브러리만 쓴다.
- **API provider의 전제(스크립트는 동봉, 키·런타임만 준비)**: 고품질 API provider 2종은 이 스킬에 동봉된 `assets/tts/gemini_tts.py`·`assets/tts/elevenlabs_tts.py`를 호출하므로 다른 스킬이나 저장소를 추가로 설치할 필요가 없다(원본은 speech-toolkit 저장소이며 사본을 동봉했다: https://github.com/Engccer/speech-toolkit ). Gemini provider(`play-tts-gemini-api.ps1`/`.sh`)는 Python + `google-genai` 패키지 + `GEMINI_API_KEY` + (속도 보정 시) `ffmpeg`, ElevenLabs provider(`play-tts-elevenlabs-api.ps1`/`.sh`)는 Python + `elevenlabs` 패키지 + `ELEVENLABS_API_KEY`가 필요하며 Windows 판은 MP3를 WAV로 바꾸기 위해 `ffmpeg`가 필수다(macOS는 `afplay`가 MP3를 재생하므로 선택). 둘 다 유료 API이고, 없거나 실패하면 OS 내장 provider로 폴백하므로 핵심 기능은 막히지 않는다. 각 스크립트 상단 `$ConverterScript`/`CONVERTER_SCRIPT`는 이 스킬 설치 폴더의 동봉 스크립트 절대 경로로 치환한다.
- **반드시 치환할 값**: `assets/hooks/*.json`의 `<USER_HOME>`은 실제 홈 경로로 바꿔야 한다. `inspect_tts_loop.py`로 실제 홈과 폴더 구조를 먼저 확인한 뒤 치환한다. 그대로 붙여넣지 않는다.
- **인코딩 주의**: `assets/windows/*.ps1`은 한글 주석 때문에 UTF-8 with BOM으로 저장돼 있다. 복사·수정 시 BOM을 보존해야 한다. BOM이 빠지면 Windows PowerShell 5.1이 파일을 ANSI로 읽어, 한글로 끝나는 줄이 다음 줄을 삼키는 파싱 오류가 생길 수 있다(`references/troubleshooting.md` 참고).
- **전제 런타임(스킬 밖이지만 필요)**: Windows는 PowerShell + 최소 1개의 SAPI 음성(기본 음성으로 충족, NaturalVoice는 선택), macOS는 `say`. 모두 OS 기본 제공이다.

## 작업 흐름

1. 기존 에이전트 홈 폴더를 먼저 점검한다.
   - `scripts/inspect_tts_loop.py --root <사용자-홈>`으로 글로벌 지침, 훅 설정, 훅 스크립트, 음성/속도 파일, 보관 폴더를 확인한다.
   - `경쟁 소비자 발견`이 나오면 먼저 제거한다. 특히 macOS에서 `WatchPaths` LaunchAgent와 Codex Stop hook이 같은 `tts-summary.txt`를 함께 읽으면 LaunchAgent가 파일을 먼저 삭제하고, 정식 Stop hook이 요약 누락으로 오인해 같은 턴에 재작성을 요구한다. 일회용 요약 파일의 소비자는 에이전트별로 하나만 둔다.
   - Claude, Codex, Gemini/Antigravity가 각각 `.claude`, `.codex`, `.gemini` 안에서 자체 스크립트와 보관 폴더를 쓰는지 확인한다.

2. 설정 파일을 설치하고 요약 언어와 재생 provider를 사용자와 확인한다.
   - **설정 파일**: `assets/windows/tts-config.txt`(또는 `assets/macos/tts-config.txt`)를 대상 에이전트 홈의 `TTS-Summary/tts-config.txt`로 복사한다. **이미 있으면 덮어쓰지 않는다.** 이 파일이 `enabled`(on/off), `speed`(1~10), `verbosity`(1~3), `interim`(on/off: 질문 선택지 안내·중간 phase 보고 여부), `provider`, 프로바이더별 음성, `language_code`의 유일한 정본이며, 값을 바꾸면 다음 턴부터 바로 적용된다.
   - **요약 언어**: 기본값은 한국어다. 사용자가 다른 언어를 원하는지 한 번 확인하고, 특별한 선택이 없으면 한국어로 진행한다. 선택한 언어는 4단계의 지침 블록(`--language`)과 설정 파일의 음성·언어 항목(`voice_sapi`/`voice_say`, `language_code`, `voice_elevenlabs`)에 함께 반영한다.
   - **재생 provider**: 기본값은 OS 내장 음성(Windows SAPI, macOS `say`)이며 무료·오프라인이다. 사용자가 고품질 음성을 원하면 Gemini API 또는 ElevenLabs API를 선택할 수 있다(세 CLI 공통, 유료 API 키 필요). 선택 결과는 설정 파일의 `provider`에 적는다: Windows `windows-sapi`(기본)/`gemini-api`/`elevenlabs-api`, macOS `say`(기본)/`gemini-api`/`elevenlabs-api`. 값이 인식되지 않으면 OS 내장 음성을 쓴다.
   - **선택지·중간 보고(interim)**: `on`이면 질문 선택지 안내와 중간 phase 보고도 읽고, `off`면 응답 완료 요약만 읽는다. 상세 정도와 무관한 독립 스위치이며, 두 소비자(`ask-question-tts.sh`, `play-tts-briefing.sh`)가 이 값을 결정론적으로 확인한다.
   - **상세 정도(verbosity)**: 요약 분량을 1~3단계로 정한다. 이 값이 실제로 반영되려면 아래 "선택 훅"의 설정 통지 훅(UserPromptSubmit)이 필요하다. Antigravity처럼 그 이벤트가 없는 CLI에서는 지침 문구로 분량을 고정한다.

3. 플랫폼별 구현 방식을 선택한다.
   - Windows: PowerShell 훅을 기본으로 사용한다. 세 CLI 모두 SAPI/NaturalVoice 음성을 기본으로 쓰고, 설정 파일의 `provider`로 Gemini API 또는 ElevenLabs API TTS로 전환할 수 있다(실패 시 SAPI 폴백). 자세한 내용은 `references/windows.md`를 본다.
   - macOS: shell hook과 `say` 음성을 기본으로 사용한다. 설정 파일의 `provider`로 Gemini API 또는 ElevenLabs API TTS로 전환할 수 있다(실패 시 `say` 폴백). 필요하면 `afplay`나 `ffmpeg` 후처리를 함께 쓴다. 자세한 내용은 `references/macos.md`를 본다.

4. 스크립트를 설치한다.
   - 처음부터 작성하지 말고 `assets/`의 검증된 템플릿을 복사해 경로만 치환한다. 각 파일 상단의 `$AgentDirName`(Windows) 또는 `AGENT_DIR_NAME`(macOS) 한 줄만 대상 에이전트 폴더명으로 바꾸면 된다(복사한 모든 파일에서 같은 값으로).
   - Windows: `assets/windows/stop-tts.ps1` + `play-tts-windows-sapi.ps1` + `tts-config.ps1`(설정 파서, 나머지가 dot-source 하므로 필수)을 대상 홈의 `hooks-windows`(Gemini는 `hooks`)에 둔다. API provider를 쓰면 `play-tts-gemini-api.ps1`/`play-tts-elevenlabs-api.ps1`도 같은 폴더에 두고 `$ConverterScript`를 치환한다. Gemini/Antigravity는 `stop-tts-wrapper.ps1`(+`.cmd` 등록 경로면 `stop-tts-wrapper.cmd`)도 함께 둔다. `.ps1`은 UTF-8 with BOM을 보존해 복사한다.
   - macOS: `assets/macos/stop-tts.sh` + `tts-config.sh`(설정 파서, 나머지가 source 하므로 필수)를 대상 홈의 훅 폴더에 둔다. API provider를 쓰면 `play-tts-gemini-api.sh`/`play-tts-elevenlabs-api.sh`도 같은 폴더에 두고 `CONVERTER_SCRIPT`를 치환한다.
   - macOS Claude Code는 `/tts` 슬래시 명령도 기본으로 설치한다: `assets/macos/tts-config-set.sh`를 같은 훅 폴더에 두고(`AGENT_DIR_NAME`은 `.claude`), `assets/claude/skills/tts/SKILL.md`를 `~/.claude/skills/tts/SKILL.md`로 복사한다. 치환할 경로는 없다. 이 명령이 있어야 사용자가 설정 파일을 열지 않고 `/tts off`·`/tts speed 8`·`/tts verbosity 2`·`/tts interim off`로 바꿀 수 있다. 새 스킬은 다음 세션부터 `/` 메뉴에 나타난다.
   - `$ConverterScript`/`CONVERTER_SCRIPT`에는 이 스킬에 동봉된 `assets/tts/gemini_tts.py`·`assets/tts/elevenlabs_tts.py`의 절대 경로를 넣는다(예: `~/.claude/skills/agent-cli-tts-summary/assets/tts/gemini_tts.py`). 이 스킬의 실제 설치 폴더를 확인해 치환한다.
   - 설치 순서와 주의(비밀값 금지 등)는 `assets/README.md`를 본다.

5. 글로벌 지침을 갱신한다.
   - `scripts/render_instruction_block.py`로 에이전트·플랫폼·요약 언어에 맞는 표준 TTS 지침 블록을 생성한다(`--language`, 기본 한국어).
   - 생성한 블록을 `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` 상단 가까이에 넣는다.
   - 지침의 임시 요약 파일 경로와 보관 폴더 경로가 실제 훅 스크립트의 경로와 일치해야 한다.

6. Stop hook을 등록한다.
   - `assets/hooks/`의 설정 샘플을 플랫폼·에이전트에 맞게 고른다(Windows: `claude.windows.settings.json` / `codex.windows.hooks.json` / `gemini.windows.settings.json`, macOS: `claude.macos.settings.json` / `codex.macos.hooks.json`. macOS Gemini 검증본은 아직 없다). 경로를 치환해 각 에이전트 설정에 병합한다. 훅 이벤트·matcher 계약은 에이전트마다 다르므로 다른 에이전트의 샘플을 경로만 바꿔 재사용하지 않는다(특히 Codex의 선택 질문 도구명은 `request_user_input`이다. `references/macos.md` 훅 등록 절 참고).
   - 훅은 에이전트가 작성한 임시 `tts-summary.txt`를 읽고, 같은 홈 아래 `TTS-Summary/txt`·`TTS-Summary/wav`에 보관하며 각각 최신 10개만 남긴다.
   - 템플릿은 실패 시 CLI 턴을 깨지 않도록 조용히 종료하고, 필요하면 fallback 알림음을 낸다.
   - Codex는 새로 추가하거나 내용이 바뀐 사용자 훅을 별도로 신뢰해야 실행한다. 대화형 신뢰 확인을 완료하거나 `hooks/list`의 해당 `key`가 `trustStatus=trusted`인지 확인한다. 같은 이벤트에 다른 훅이 있으면 화면의 `Completed` 한 줄만으로 목표 훅 실행을 판정하지 않는다.

7. 끝까지 검증한다.
   - 짧은 에이전트 응답을 한 번 발생시킨다.
   - 임시 요약 파일이 생성되고 훅에 의해 처리되는지 확인한다.
   - `TTS-Summary/txt`와 `TTS-Summary/wav`에 새 보관본이 생기는지 확인한다.
   - macOS Claude Code는 새 세션에서 `/tts`를 쳐서 현재 설정 한 줄이 나오는지 확인한다.
   - Windows에서는 음성 재생 때 별도 콘솔 창이 뜨지 않는지도 확인한다.

## 선택 훅

기본 요약 루프 위에 필요하면 다음 보조 훅을 더한다. 둘 다 기본 루프와 같은 음성/속도 파일을 재사용하며, 없어도 요약 재생 자체는 동작한다.

- **요약 누락 가드 (Stop hook 내장)**: 에이전트가 `tts-summary.txt`를 쓰지 않고 턴을 끝내면, 아직 한 번도 재요청하지 않은 경우에 한해 Stop hook이 `exit 2`로 응답을 차단하고 요약 작성을 요구한다. Stop hook payload(stdin)의 `stop_hook_active`가 true면 이미 한 번 재요청한 것이므로 무한루프를 피해 통과한다. `assets/macos/stop-tts.sh`와 `assets/windows/stop-tts.ps1`에 들어 있다. 이 가드가 발동하려면 훅 명령이 payload를 stdin으로 받을 수 있어야 한다.
- **설정 통지 (UserPromptSubmit hook)**: 매 턴 설정 파일을 읽어 사용 여부와 상세 정도를 `[tts-config]`로 시작하는 한 줄로 에이전트에 알린다. Stop hook 시점에는 요약이 이미 쓰인 뒤라 `verbosity`를 반영할 수 없으므로 이 훅이 담당한다. `assets/windows/tts-config-context.ps1`, `assets/macos/tts-config-context.sh`. Claude Code와 macOS Codex 0.149.1에서 검증했고, Antigravity(agy)에는 `UserPromptSubmit` 이벤트 자체가 없다. Codex는 일반 텍스트 stdout을 실패로 처리하므로 `hookSpecificOutput.additionalContext` JSON을 출력해야 한다.
- **질문 선택지 음성 안내 (PreToolUse hook)**: 선택 질문 도구 호출 직전, 질문 본문과 선택지 라벨을 한국어로 조립해 음성으로 읽어 준다(선택지 설명은 스크린리더 TUI 탐색과 중복되므로 생략). 도구 호출을 절대 차단하지 않고 백그라운드로 재생한다. 설정의 `interim=off`면 발화하지 않는다. macOS 스크립트는 `assets/macos/ask-question-tts.sh` 하나로 Claude·Codex 공용이며, 등록 matcher만 에이전트별 실제 도구명(Claude `AskUserQuestion`, Codex `request_user_input`)을 쓴다. Windows 대응본은 아직 없다.
- **`/tts` 슬래시 명령 (Claude Code 스킬, macOS는 4단계에서 기본 설치)**: 설정 파일을 열지 않고 대화 중에 사용 여부·속도·상세 정도·선택지·중간 보고 여부를 바꾼다(`/tts off`, `/tts speed 8`, `/tts verbosity 2`, `/tts interim off`, 인자 없으면 현재 설정 표시). SKILL.md의 `!` 접두 줄이 설정기를 모델 호출 없이 실행하므로 결정론적으로 값이 바뀌고, 훅이 매 턴 설정 파일을 새로 읽어 같은 턴의 재생부터 적용된다. `disable-model-invocation: true`라 사용자가 직접 칠 때만 동작한다. 설정은 컴퓨터 전체에 하나뿐이라 세션별 제어는 아니다. Codex 커스텀 프롬프트는 셸 실행을 지원하지 않고 Windows 설정기도 아직 없다.

## 훅 제한 시간 제약 (필수)

이 루프는 **재생이 끝날 때까지 Stop hook을 붙잡는 구조**다(`afplay`/SAPI를 동기 실행). 따라서 다음 부등식이 반드시 성립해야 한다.

```
훅 timeout  >  최대 요약 재생 시간 + 음성 생성 시간
```

부등식이 깨지면 CLI가 훅을 강제 종료하면서 재생 프로세스까지 함께 죽어 **음성이 중간에 뚝 끊긴다**. 음성 파일 자체는 정상 생성되므로 파일만 보면 원인을 못 찾는다.

- **판정법**: 보관된 요약 글자 수와 WAV 길이의 비율을 본다. 비율이 일정한데 귀로는 끊긴다면 생성이 아니라 **재생 중단**이다(macOS `say -r 400` 한국어 기준 약 15.5자/초).
- **권장값**: `timeout: 300`. 요약 1,000자가 약 65초이므로 4,000자까지 여유가 있다. `assets/hooks/*.json`은 이 값으로 배포한다.
- **요약 길이도 함께 관리한다**: 글로벌 지침의 분량 규칙(복잡한 작업도 7~10문장)을 지키면 재생이 60초를 넘지 않는다. 지침을 어겨 요약이 길어진 것이 실제 사고의 방아쇠였다.
- **Windows Gemini/Antigravity 판은 다른 방식으로 이미 우회한다**: `stop-tts-wrapper.ps1`이 합성만 하고 WAV를 숨김 분리 재생해 훅을 즉시 반환시킨다. 그 계열은 timeout 제약에서 자유롭다.
- ⚠ macOS에서 재생을 분리(detach)하려는 시도는 권장하지 않는다. `setsid`가 없고, `nohup`·`start_new_session` 모두 CLI의 훅 종료 시 함께 정리되는 것을 실측했다(2026-08-01). timeout 상향이 확실하고 단순한 해법이다.

## 참고 문서

- `references/architecture.md`: 공통 루프 구조, 에이전트별 경로, 외부 의존성 원칙.
- `references/windows.md`: Windows 훅, 음성/provider 파일, 숨김 재생, Gemini API TTS 구성.
- `references/macos.md`: macOS `say` 기반 구성과 음성 선택 예시.
- `references/instruction-blocks.md`: 글로벌 지침에 넣을 표준 TTS 요약 규칙.
- `references/troubleshooting.md`: 구현 과정에서 확인한 실패 유형과 해결책.

## 스크립트

- `scripts/inspect_tts_loop.py`: 로컬 에이전트 TTS 폴더 구조를 진단한다.
- `scripts/render_instruction_block.py`: 대상 에이전트·플랫폼·요약 언어에 맞는 글로벌 지침 블록을 출력한다(`--language`, 기본 한국어. 그 외 언어는 영어 블록에 해당 언어를 지정).
- `scripts/test_render_instruction_block.py`: 지침 블록의 경로·순서 규칙·일회용 파일 계약이 유지되는지 검증한다(`python scripts/test_render_instruction_block.py`).
- `scripts/test_tts_config_context.py`: Claude 일반 텍스트와 Codex `hookSpecificOutput.additionalContext` JSON 출력 계약, TTS 끔, 기본 상세 정도를 검증한다(`python scripts/test_tts_config_context.py`).
- `scripts/test_macos_tts_config.py`: macOS 속도 곡선의 고정점과 2배 초과 `atempo` 체인을 검증한다(`python scripts/test_macos_tts_config.py`).
- `scripts/test_tts_config_set.py`: `/tts` 설정기의 값 변경·범위 검증·주석 보존·누락 키 추가를 검증한다(`python scripts/test_tts_config_set.py`).
- `scripts/test_tts_interim.py`: `interim=off`가 질문 선택지 안내와 중간 phase 보고를 막고, 키가 없으면 켬으로 동작하는지 검증한다(`python scripts/test_tts_interim.py`).
- `scripts/test_inspect_tts_loop.py`: macOS LaunchAgent가 Stop hook과 같은 일회용 요약 파일을 소비하는 충돌을 진단기가 탐지하는지 검증한다(`python scripts/test_inspect_tts_loop.py`).

## 자산

검증된 훅·재생 스크립트와 훅 설정 샘플을 `assets/`에 둔다. 설치 시 처음부터 작성하지 말고 복사해 경로만 치환한다. 파일 지도와 설치 순서는 `assets/README.md` 참고.

- `assets/windows/`: Windows용 `tts-config.txt`(설정 파일 템플릿), `tts-config.ps1`(설정 파서), `tts-config-context.ps1`(설정 통지 훅), `stop-tts.ps1`, provider 3종(SAPI/Gemini API/ElevenLabs API), Gemini/Antigravity용 wrapper 2종(`stop-tts-wrapper.ps1`: 합성 전용 실행 + WAV 숨김 분리 재생 + JSON stdout, `stop-tts-wrapper.cmd`: `.cmd` 등록 경로용).
- `assets/macos/`: macOS `tts-config.txt`(설정 파일 템플릿), `tts-config.sh`(설정 파서), `tts-config-context.sh`(설정 통지 훅), `stop-tts.sh`(기본 `say`), provider 2종(Gemini API/ElevenLabs API), 질문 선택지 음성 안내 `ask-question-tts.sh`, 통합 설정을 따르는 중간 phase 보고 `play-tts-briefing.sh`, `/tts` 슬래시 명령이 부르는 설정기 `tts-config-set.sh`.
- `assets/claude/skills/tts/`: Claude Code `/tts` 슬래시 명령 스킬(`SKILL.md`). `~/.claude/skills/tts/`에 복사한다.
- `assets/hooks/`: Claude·Codex·Gemini 훅 등록 샘플(비밀값 미포함).

## 에이전트 인터페이스 메타

`agents/openai.yaml`은 Codex/OpenAI 계열 에이전트가 이 스킬을 노출할 때 쓰는 표시 이름·기본 프롬프트 정의다. Claude Code 동작에는 영향이 없으며, 멀티 에이전트 호환을 위한 부가 메타데이터다.

## 관련 프로젝트

시각장애 사용자를 위한 에이전트 스킬 번들 [skills-for-the-blind](https://github.com/Engccer/skills-for-the-blind)의 멤버 스킬이다.
