# agent-cli-tts-summary

로컬 코딩 에이전트 CLI(Claude Code, Codex CLI, Gemini CLI, Antigravity CLI)의 응답 요약을 음성으로 듣기 위한 훅 기반 TTS 루프를 설치, 점검, 이식, 복구하는 스킬이다. 에이전트가 턴을 끝낼 때 요약을 임시 파일에 쓰면, Stop hook이 그 파일을 읽어 음성을 생성·재생하고 보관본을 정리한다. 요약 언어는 설치 시 선택할 수 있고 기본값은 한국어다. 화면을 보지 않고도 매 턴의 작업 결과를 음성으로 확인하려는 시각장애인 스크린 리더 사용자를 1차 대상으로 한다.

핵심 설계 원칙은 에이전트별 내부 완결성이다. Claude, Codex, Gemini/Antigravity가 서로의 스크립트나 보관 폴더를 침범하지 않도록 각 에이전트 홈(`.claude`, `.codex`, `.gemini`) 안에 완결된 루프를 둔다. 기본 음성 재생은 OS 내장 기능(Windows SAPI, macOS `say`)을 사용하므로 외부 TTS 앱이나 API 키, 비용 없이 쓸 수 있다. 필요한 런타임과 패키지는 아래 전제조건을 따른다. 고품질 음성을 원하면 세 CLI 어디서나 동일하게 설정 파일의 `provider` 한 줄로 Gemini API 또는 ElevenLabs API provider로 전환할 수 있고(유료 API 키 필요), API가 실패하면 OS 내장 음성으로 자동 폴백한다. 사용 여부·속도·요약 상세 정도·선택지와 중간 보고 여부·프로바이더·음성은 에이전트 홈의 `TTS-Summary/tts-config.txt` 한 파일에서 관리한다.

**English:** agent-cli-tts-summary installs, inspects, ports, and repairs a hook-based text-to-speech loop for local coding-agent CLIs (Claude Code, Codex CLI, Gemini CLI, Antigravity CLI). At the end of each turn the agent writes a short summary to a temp file; a Stop hook reads it, speaks it, and keeps the last ten TXT and WAV copies under each agent's own home folder. The summary language is selectable at setup (Korean by default). It is built for blind screen-reader users who want to hear what each turn accomplished, and it runs for free on the operating system's built-in voices (Windows SAPI, macOS `say`); on every CLI you can optionally switch to a high-quality Gemini API or ElevenLabs API voice by changing one line in the settings file, with automatic fallback to the built-in voice. On/off, speed, summary verbosity, interim announcements, provider, and voice all live in a single `TTS-Summary/tts-config.txt` under each agent home.

## 무엇을 하나

- 새 컴퓨터에 TTS 요약 루프를 처음부터 설치한다(요약 언어와 재생 provider를 설치 시 선택, 기본값은 한국어 + OS 내장 음성).
- 기존 머신의 루프를 다른 에이전트나 다른 OS로 이식한다.
- 사용 여부(on/off), 말하기 속도, 요약 상세 정도, 선택지·중간 보고 여부, 프로바이더, 음성, 언어 코드를 설정 파일 하나(`TTS-Summary/tts-config.txt`)로 관리한다. 요약 언어는 지침 블록을 다시 생성해 바꾸고, 이 파일에서는 음성과 언어 코드를 맞춘다.
- OS 내장 음성을 고품질 Gemini API 또는 ElevenLabs API 음성으로 전환한다(세 CLI 공통, 설정 파일의 `provider`).
- 각 에이전트 홈 안에서 루프가 완결되는지 점검한다(`scripts/inspect_tts_loop.py`).
- 음성 재생 실패를 진단하고 복구한다.
- 요약 누락 방지 가드나 질문 선택지 음성 안내 같은 보조 훅을 더한다.
- Claude Code에서는 `/tts`로 설정을 바꾸고 `/tts-replay`로 직전 요약 음성을 한 번 더 듣는다.
- macOS Codex에서는 `/skills` 메뉴의 `codex-tts`·`codex-tts-replay` 또는 `$codex-tts off`·`$codex-tts-replay`로 같은 기능을 사용한다. 설치: `python3 scripts/install_codex_commands.py`. [Codex 명령 안내](references/codex-commands.md).

## macOS 낭독 명령

pi 1.1.0 이상은 저장소 루트에서 `python3 scripts/install_pi_tts.py`로 설치한다. 새 세션 또는 `/reload` 후 `/tts`, `/tts on|off`, `/tts speed 7.5`, `/tts verbosity 2`, `/tts-replay`, `/tts-pause`를 사용한다. 로컬 모델의 한국어 요약 작성과 macOS 내장 음성을 연결하며, 설정·보관 파일은 `~/.pi/agent/`에 둔다. [pi 설치와 검증](references/pi.md).

| 기능 | Claude Code | Codex CLI | agy |
| --- | --- | --- | --- |
| 직전 요약 다시 듣기 | `/tts-replay` | `$codex-tts-replay` | `/tts-replay` |
| 마지막 완료 응답 전문 읽기 | `/tts-read` | `$codex-tts-read` | `/tts-read` |
| 현재 낭독 중지 | `/tts-pause` | `$codex-tts-pause` | `/tts-pause` |

`read`는 현재 대화의 마지막 완료 응답을 읽는다. 코드 블록은 종류만 안내하며, TTS 요약 파일·도구 결과·중간 보고는 읽지 않는다. `pause`는 해당 도구의 현재 요약·replay·read를 종료한다. 재개 지점은 저장하지 않으며 다음 응답의 자동 요약 설정은 유지한다. 이 전문 읽기·중지 명령은 macOS Claude Code·Codex CLI·agy용이다.

기존 TTS 루프와 설정 파일을 준비한 뒤 저장소에서 실행한다. `--agent`에는 사용할 도구 하나를 지정한다.

```bash
python3 -m pip install 'markdown-it-py>=3,<5'
python3 scripts/install_macos_commands.py --agent claude --update-stop-hook
```

Codex는 `--agent codex`, agy는 `--agent agy`를 쓴다. 설치기는 설정과 훅 등록을 보존하고, 변경할 파일을 백업한다. 요약 낭독도 중지하려면 `--update-stop-hook`이 필요하다. 상세: [macOS](references/macos.md#세-도구의-전문-낭독과-중지), [Codex](references/codex-commands.md), [agy](references/agy-commands.md).

## 동작 방식

1. 글로벌 지침(`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`)이 에이전트에게 턴 종료 요약을 임시 파일에 쓰라고 지시한다.
2. 에이전트가 턴 끝에서 `tts-summary.txt`를 작성한다.
3. Stop hook이 턴 종료 후 그 파일을 읽는다.
4. 로컬 TTS 스크립트가 음성을 생성·재생한다.
5. 훅이 요약 TXT는 `TTS-Summary/txt`, 음성 WAV는 `TTS-Summary/wav`에 보관하고 각각 최신 10개만 남긴 뒤, 임시 파일은 삭제한다. 임시 파일은 턴 하나짜리이므로 에이전트는 매 턴 새로 만든다.

자동 요약 재생은 Stop hook이 담당한다. macOS에서는 훅이 합성·재생을 별도 작업으로 넘겨, 낭독 중에도 같은 CLI에서 중지 명령을 실행할 수 있다. 사용자가 직접 호출한 `read`·`replay`는 해당 명령이 재생을 시작하며, 그 턴에는 새 요약을 작성하지 않는다.

## 지원 플랫폼

- **Windows**: PowerShell Stop hook과 `System.Speech`(SAPI/NaturalVoice) 음성. 설정 파일의 `provider`로 Gemini API 또는 ElevenLabs API TTS로 전환할 수 있고, 실패 시 SAPI로 폴백한다. 상세는 `references/windows.md`.
- **macOS**: shell Stop hook과 내장 `say` 음성. 설정 파일의 `provider`로 Gemini API 또는 ElevenLabs API TTS로 전환할 수 있고, 실패 시 `say`로 폴백한다. 필요하면 `afconvert`/`afplay`/`ffmpeg`로 후처리한다. 상세는 `references/macos.md`.

## 설치

```bash
npx skills add Engccer/agent-cli-tts-summary -g
```

설치 후 `assets/`의 검증된 템플릿을 대상 에이전트 홈에 복사하고 경로만 치환한다. 처음부터 새로 작성하지 않는다. 설치 순서는 `SKILL.md`의 "작업 흐름", 파일 지도와 주의사항은 `assets/README.md`를 본다.

## 전제조건

기본 음성 재생에는 외부 TTS 앱이나 API 키가 필요 없다. 플랫폼별 런타임과 전문 읽기용 패키지는 아래와 같다.

- **Windows**: PowerShell과 SAPI 음성 최소 1개(기본 음성으로 충족, NaturalVoice는 선택).
- **macOS**: Python 3와 내장 `say`·`afconvert`·`afplay`·`launchctl`. 전문 읽기에는 같은 Python 환경에 `markdown-it-py` 3.x 또는 4.x가 필요하다.

선택형 고품질 API provider 2종은 변환 스크립트가 이 저장소의 `assets/tts/`에 동봉돼 있어 별도 스킬·저장소 설치가 필요 없다(원본: [speech-toolkit](https://github.com/Engccer/speech-toolkit)). 둘 다 유료 API이며, 없거나 실패하면 OS 내장 음성으로 폴백한다.

- **Gemini API** (`play-tts-gemini-api.ps1`/`.sh`): 동봉 `assets/tts/gemini_tts.py` + Python + `GEMINI_API_KEY`, 속도 보정 시 `ffmpeg`. Windows 판은 `google-genai` 패키지도 필요하다.
- **ElevenLabs API** (`play-tts-elevenlabs-api.ps1`/`.sh`): 동봉 `assets/tts/elevenlabs_tts.py` + Python(`elevenlabs` 패키지) + `ELEVENLABS_API_KEY`. Windows 판은 MP3를 WAV로 바꾸기 위해 `ffmpeg` 필수(macOS는 `afplay`가 MP3를 재생하므로 선택).

## 구성

- `SKILL.md`: 스킬 진입점과 작업 흐름.
- `assets/`: 훅·재생 스크립트 템플릿(`windows/`, `macos/`), 동봉 변환 스크립트(`tts/`), Claude 명령 스킬(`claude/`), Codex·agy 명령 템플릿(`codex/`, `agy/`), 훅 등록 샘플(`hooks/`).
- `scripts/`: 폴더 구조 진단(`inspect_tts_loop.py`), 글로벌 지침 블록 생성(`render_instruction_block.py`), macOS 세 도구의 명령 설치(`install_macos_commands.py`, Codex 전용 진입점 `install_codex_commands.py`), 테스트.
- `references/`: 구조, 플랫폼별 구성, 지침 블록, 문제 해결 문서.
- `agents/`: Codex·OpenAI 계열 에이전트가 이 스킬을 노출할 때 쓰는 표시 이름·기본 프롬프트 정의.

## 관련 프로젝트

시각장애 사용자를 위한 에이전트 스킬 번들 [skills-for-the-blind](https://github.com/Engccer/skills-for-the-blind)의 멤버 스킬이다. 각 스킬은 독립적으로도 설치해 쓸 수 있다.

## License

MIT (c) 2026 Engccer
