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

## 외부 런타임 의존성

이 루프는 외부 TTS CLI나 앱에 런타임 의존하지 않는다. 재생은 OS 내장 기능(Windows SAPI/`System.Speech`, macOS `say`)이나 명시적으로 호출하는 Gemini API provider(`gemini_tts.py`)만 사용한다. `assets/`의 템플릿은 모두 중립 이름(`stop-tts`, `TTS_NO_PLAY`)을 쓴다.

오래된 다른 머신을 점검·마이그레이션할 때, 기존 훅 스크립트가 정체불명의 외부 실행 파일을 직접 호출하는 부분이 보이면 그것이 실제 의존성인지 단순 이름 흔적인지 구분한다. 글로벌 지침에는 실제로 호출되는 도구만 적고, 흔적성 이름은 의존성처럼 적지 않는다. 가장 깔끔한 정리는 기존 잔재를 그대로 두지 말고 `assets/`의 중립 템플릿으로 새로 설치하는 것이다.

## agents/openai.yaml

저장소 루트의 `agents/openai.yaml`은 Codex/OpenAI 계열 에이전트가 이 스킬을 목록에 노출할 때 쓰는 인터페이스 메타데이터(표시 이름, 짧은 설명, 기본 프롬프트)다. Claude Code의 스킬 동작에는 관여하지 않으며, 같은 루프를 여러 에이전트에서 동일하게 부르기 위한 부가 정의일 뿐이다.
