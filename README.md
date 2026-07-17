# agent-cli-tts-summary

로컬 코딩 에이전트 CLI(Claude Code, Codex CLI, Gemini CLI, Antigravity CLI)의 응답 요약을 음성으로 듣기 위한 훅 기반 TTS 루프를 설치, 점검, 이식, 복구하는 스킬이다. 에이전트가 턴을 끝낼 때 요약을 임시 파일에 쓰면, Stop hook이 그 파일을 읽어 음성을 생성·재생하고 보관본을 정리한다. 요약 언어는 설치 시 선택할 수 있고 기본값은 한국어다. 화면을 보지 않고도 매 턴의 작업 결과를 음성으로 확인하려는 시각장애인 스크린 리더 사용자를 1차 대상으로 한다.

핵심 설계 원칙은 에이전트별 내부 완결성이다. Claude, Codex, Gemini/Antigravity가 서로의 스크립트나 보관 폴더를 침범하지 않도록 각 에이전트 홈(`.claude`, `.codex`, `.gemini`) 안에 완결된 루프를 둔다. 재생은 외부 TTS 앱에 런타임 의존하지 않고 기본적으로 OS 내장 기능(Windows SAPI, macOS `say`)만으로 동작하므로 추가 설치나 API 키, 비용 없이 쓸 수 있다. 고품질 음성을 원하면 세 CLI 어디서나 동일하게 에이전트 홈의 `tts-provider.txt` 한 줄로 Gemini API 또는 ElevenLabs API provider로 전환할 수 있고(유료 API 키 필요), API가 실패하면 OS 내장 음성으로 자동 폴백한다.

**English:** agent-cli-tts-summary installs, inspects, ports, and repairs a hook-based text-to-speech loop for local coding-agent CLIs (Claude Code, Codex CLI, Gemini CLI, Antigravity CLI). At the end of each turn the agent writes a short summary to a temp file; a Stop hook reads it, speaks it, and keeps the last ten TXT and WAV copies under each agent's own home folder. The summary language is selectable at setup (Korean by default). It is built for blind screen-reader users who want to hear what each turn accomplished, and it runs for free on the operating system's built-in voices (Windows SAPI, macOS `say`); on every CLI you can optionally switch to a high-quality Gemini API or ElevenLabs API voice via a one-line `tts-provider.txt`, with automatic fallback to the built-in voice.

## 무엇을 하나

- 새 컴퓨터에 TTS 요약 루프를 처음부터 설치한다(요약 언어와 재생 provider를 설치 시 선택, 기본값은 한국어 + OS 내장 음성).
- 기존 머신의 루프를 다른 에이전트나 다른 OS로 이식한다.
- OS 내장 음성을 고품질 Gemini API 또는 ElevenLabs API 음성으로 전환한다(세 CLI 공통, `tts-provider.txt`).
- 각 에이전트 홈 안에서 루프가 완결되는지 점검한다(`scripts/inspect_tts_loop.py`).
- 음성 재생 실패를 진단하고 복구한다.
- 요약 누락 방지 가드나 질문 선택지 음성 안내 같은 보조 훅을 더한다.

## 동작 방식

1. 글로벌 지침(`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`)이 에이전트에게 턴 종료 요약을 임시 파일에 쓰라고 지시한다.
2. 에이전트가 턴 끝에서 `tts-summary.txt`를 작성한다.
3. Stop hook이 턴 종료 후 그 파일을 읽는다.
4. 로컬 TTS 스크립트가 음성을 생성·재생한다.
5. 훅이 요약 TXT는 `TTS-Summary/txt`, 음성 WAV는 `TTS-Summary/wav`에 보관하고 각각 최신 10개만 남긴다.

에이전트 본문 응답 중에는 TTS를 직접 호출하지 않는다. 재생을 Stop hook의 책임으로 분리해 응답 흐름을 예측 가능하게 유지한다.

## 지원 플랫폼

- **Windows**: PowerShell Stop hook과 `System.Speech`(SAPI/NaturalVoice) 음성. `tts-provider.txt`로 Gemini API 또는 ElevenLabs API TTS로 전환할 수 있고, 실패 시 SAPI로 폴백한다. 상세는 `references/windows.md`.
- **macOS**: shell Stop hook과 내장 `say` 음성. `tts-provider.txt`로 Gemini API 또는 ElevenLabs API TTS로 전환할 수 있고, 실패 시 `say`로 폴백한다. 필요하면 `afconvert`/`afplay`/`ffmpeg`로 후처리한다. 상세는 `references/macos.md`.

## 설치

```bash
npx skills add Engccer/agent-cli-tts-summary -g
```

설치 후 `assets/`의 검증된 템플릿을 대상 에이전트 홈에 복사하고 경로만 치환한다. 처음부터 새로 작성하지 않는다. 설치 순서와 주의사항은 `assets/README.md`를 본다.

## 전제조건

기본 루프(OS 내장 음성)는 자체 완결적이라 추가 설치 없이 동작한다. OS 기본 제공 런타임만 있으면 된다.

- **Windows**: PowerShell과 SAPI 음성 최소 1개(기본 음성으로 충족, NaturalVoice는 선택).
- **macOS**: 내장 `say`.

선택형 고품질 API provider 2종은 변환 스크립트가 이 저장소의 `assets/tts/`에 동봉돼 있어 별도 스킬·저장소 설치가 필요 없다(원본: [speech-toolkit](https://github.com/Engccer/speech-toolkit)). 둘 다 유료 API이며, 없거나 실패하면 OS 내장 음성으로 폴백한다.

- **Gemini API** (`play-tts-gemini-api.ps1`/`.sh`): 동봉 `assets/tts/gemini_tts.py` + Python(`google-genai` 패키지) + `GEMINI_API_KEY`, 속도 보정 시 `ffmpeg`.
- **ElevenLabs API** (`play-tts-elevenlabs-api.ps1`/`.sh`): 동봉 `assets/tts/elevenlabs_tts.py` + Python(`elevenlabs` 패키지) + `ELEVENLABS_API_KEY`. Windows 판은 MP3를 WAV로 바꾸기 위해 `ffmpeg` 필수(macOS는 `afplay`가 MP3를 재생하므로 선택).

## 선택 훅

기본 요약 루프 위에 필요하면 더한다. 둘 다 없어도 요약 재생 자체는 동작한다.

- **요약 누락 가드(Stop hook 내장)**: 에이전트가 요약을 쓰지 않고 턴을 끝내면, 아직 재요청하지 않은 경우에 한해 `exit 2`로 응답을 되돌려 요약 작성을 요구한다.
- **질문 선택지 음성 안내(PreToolUse hook)**: `AskUserQuestion` 호출 직전 질문 본문과 선택지 라벨을 한국어로 읽어 준다. 도구 호출을 차단하지 않고 백그라운드로 재생한다. macOS 검증본은 `assets/macos/ask-question-tts.sh`.

## 구성

- `SKILL.md`: 스킬 진입점과 작업 흐름.
- `assets/`: 검증된 훅·재생 스크립트 템플릿(`windows/`, `macos/`)과 훅 등록 샘플(`hooks/`).
- `scripts/`: 폴더 구조 진단(`inspect_tts_loop.py`)과 글로벌 지침 블록 생성(`render_instruction_block.py`).
- `references/`: 구조, 플랫폼별 구성, 지침 블록, 문제 해결 문서.

## 관련 프로젝트

시각장애 사용자를 위한 에이전트 스킬 번들 [skills-for-the-blind](https://github.com/Engccer/skills-for-the-blind)의 멤버 스킬이다. 각 스킬은 독립적으로도 설치해 쓸 수 있다.

## License

MIT (c) 2026 Engccer
