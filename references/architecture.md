# 구조

## 기본 루프

재사용 가능한 TTS 요약 루프는 다섯 부분으로 구성된다.

1. 글로벌 지침 파일이 에이전트에게 턴 종료 브리핑을 임시 파일에 쓰라고 지시한다.
2. 에이전트가 턴 끝에서 `tts-summary.txt`를 파일 편집으로 작성한다.
3. Stop hook이 턴 종료 후 실행되어 임시 요약 파일을 읽는다.
4. 로컬 TTS 스크립트가 음성을 생성하고 재생한다.
5. 훅이 요약 TXT는 `TTS-Summary/txt`, 음성 WAV는 `TTS-Summary/wav`에 보관하고 각각 최신 10개만 남긴다.

에이전트 본문 응답 중에는 TTS 스크립트를 직접 호출하지 않는다. 직접 재생은 Stop hook의 책임으로 두어야 응답 흐름이 예측 가능하고, 요약 작성과 음성 재생이 분리된다.

## 홈 폴더 경계

가능하면 각 CLI는 자기 홈 폴더 안에 완결된 루프를 가져야 한다.

| 에이전트 | 글로벌 지침 | 임시 요약 | 보관 폴더 |
| --- | --- | --- | --- |
| Claude Code | `.claude/CLAUDE.md` | `.claude/tts-summary.txt` | `.claude/TTS-Summary/txt`, `.claude/TTS-Summary/wav` |
| Codex CLI | `.codex/AGENTS.md` | `.codex/tts-summary.txt` | `.codex/TTS-Summary/txt`, `.codex/TTS-Summary/wav` |
| Gemini CLI | `.gemini/GEMINI.md` | `.gemini/tts-summary.txt` | `.gemini/TTS-Summary/txt`, `.gemini/TTS-Summary/wav` |
| Antigravity CLI | 보통 `.gemini/GEMINI.md` 공유 | 보통 `.gemini/tts-summary.txt` 공유 | 보통 `.gemini/TTS-Summary/txt`, `.gemini/TTS-Summary/wav` 공유 |

Antigravity CLI는 별도 상태 폴더로 `.antigravitycli`를 둘 수 있지만, 관찰된 구성에서는 훅과 글로벌 지침이 Gemini 호환 설정인 `.gemini` 아래 파일들과 연결되어 있었다.

## 재생 provider 선택

세 CLI가 동일한 provider 옵션을 갖는다. 선택은 에이전트 홈의 `tts-provider.txt` 한 줄로 한다.

| 값 | 음성 | 비용 | 외부 의존 |
| --- | --- | --- | --- |
| `windows-sapi`(Windows 기본) / `say`(macOS 기본) | OS 내장 | 무료·오프라인 | 없음 |
| `gemini-api` | Gemini API TTS | 유료 API | speech-toolkit `TTS/gemini_tts.py`, `GEMINI_API_KEY`, (속도 보정) ffmpeg |
| `elevenlabs-api` | ElevenLabs API TTS | 유료 API | speech-toolkit `TTS/elevenlabs_tts.py`, `ELEVENLABS_API_KEY`, ffmpeg(Windows 필수, macOS 선택) |

규약: Stop hook은 `tts-provider.txt`를 읽어 자기와 같은 폴더의 provider 스크립트를 호출한다. 파일이 없거나 값이 인식되지 않으면 OS 내장 provider를 쓴다. provider 스크립트는 성공 시 exit 0, 실패 시 exit 1을 내고, API provider가 실패하면 Stop hook이 OS 내장 provider로 런타임 폴백해 요약이 항상 들리게 한다. 각 provider는 자기 음성 설정 파일(`tts-voice-sapi.txt`/`tts-voice-say.txt`, `tts-voice-gemini.txt`+`tts-language-code.txt`, `tts-voice-elevenlabs.txt`)을 스스로 읽으므로 Stop hook은 요약 텍스트만 넘긴다.

## 요약 언어

요약 언어는 글로벌 지침 블록이 정한다(`scripts/render_instruction_block.py --language`, 기본 한국어). 훅 스크립트는 특정 언어를 강제하지 않으며, 요약 누락 가드 메시지도 "글로벌 지침의 규칙에 따라"라고만 요구한다. 언어를 바꾸면 provider별 음성 설정(SAPI/`say` 음성 이름, Gemini `tts-language-code.txt`, ElevenLabs 음성 이름)도 그 언어에 맞게 함께 바꾼다.

## 외부 런타임 의존성

이 루프는 외부 TTS CLI나 앱에 런타임 의존하지 않는다. 재생은 OS 내장 기능(Windows SAPI/`System.Speech`, macOS `say`)이나 명시적으로 호출하는 API provider(speech-toolkit( https://github.com/Engccer/speech-toolkit )의 `TTS/gemini_tts.py`·`TTS/elevenlabs_tts.py`)만 사용한다. 글로벌 지침에는 실제로 호출되는 도구만 적는다.

## agents/openai.yaml

저장소 루트의 `agents/openai.yaml`은 Codex/OpenAI 계열 에이전트가 이 스킬을 목록에 노출할 때 쓰는 인터페이스 메타데이터(표시 이름, 짧은 설명, 기본 프롬프트)다. Claude Code의 스킬 동작에는 관여하지 않으며, 같은 루프를 여러 에이전트에서 동일하게 부르기 위한 부가 정의일 뿐이다.
