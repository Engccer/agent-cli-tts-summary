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

## AgentVibes 유래와 현재 의존성

이 구성은 AgentVibes에서 영감을 받은 스크립트에서 출발했기 때문에 예전 파일명, wrapper 이름, 로그 라벨, 환경 변수에 `agentvibes`나 `AGENTVIBES`가 남아 있을 수 있다. 하지만 그런 이름이 곧 AgentVibes CLI나 앱이 필요하다는 뜻은 아니다.

새 컴퓨터를 점검할 때는 다음을 구분한다.

- 역사적 흔적: AgentVibes를 언급하는 파일명, 주석, 환경 변수, 로그 라벨.
- 실제 런타임 의존성: `agentvibes`, `agentvibes.exe`, 패키지 entry point 같은 실행 파일을 직접 호출하는 부분.

실제 실행 호출이 없다면 글로벌 지침에는 AgentVibes를 필수 도구처럼 적지 않는다. 혼동을 줄이려면 “AgentVibes 계열 이름은 역사적 흔적일 뿐 현재 외부 런타임 의존성은 아니다” 정도로만 참고 문서에 남긴다.
