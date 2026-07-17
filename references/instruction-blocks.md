# 지침 블록

Claude, Codex, Gemini, Antigravity의 음성 요약이 일관되게 들리도록 같은 요약 형식 규칙을 사용한다.

경로가 반영된 지침 블록은 다음처럼 생성한다.

```bash
# --home 생략 시 현재 사용자 홈에서 자동으로 경로를 잡는다.
python scripts/render_instruction_block.py --agent codex --platform windows
# 다른 홈을 지정하려면 --home 으로 덮어쓴다.
python scripts/render_instruction_block.py --agent codex --platform windows --home <USER_HOME>/.codex
# 요약 언어를 바꾸려면 --language 를 준다(기본 한국어).
python scripts/render_instruction_block.py --agent claude --platform macos --language English
```

## 요약 언어 선택

- `--language` 기본값은 한국어이며, 한국어를 뜻하는 값(`ko`/`korean`/`한국어` 등)이면 한국어 블록을 출력한다.
- 그 외 값(예: `English`, `日本語`)이면 규칙 본문은 영어 블록으로 출력하고 마지막 `Language:` 줄에 해당 언어를 지정한다. 임의 언어로 블록 전체를 번역할 수는 없으므로, 규칙은 에이전트가 확실히 이해하는 영어로 두고 요약 언어만 지시하는 방식이다.
- 언어를 바꾸면 provider별 음성 설정(SAPI/`say` 음성 이름, Gemini `tts-language-code.txt`, ElevenLabs 음성 이름)도 그 언어에 맞게 함께 바꾼다. 훅 스크립트 자체는 언어를 강제하지 않는다.

## 표준 요약 규칙

- **작성 순서: 요약 파일을 먼저 쓰고, 본문 답변을 턴의 마지막 출력으로 낸다.** 본문 답변 뒤에 요약 파일 쓰기(또는 어떤 도구 호출)가 오면, 마지막 텍스트 메시지만 제대로 보여주는 에이전트 CLI(Claude Code 실측, 2026-07-17)에서 본문이 도구 호출 사이 텍스트로 밀려 화면·스크린 리더에서 유실된다. Stop hook은 턴 종료 후 파일만 읽으므로 요약을 먼저 써도 무방하다.
- TTS 요약은 지침 블록에 지정된 언어(기본 한국어)로 작성한다.
- 자기 인용이나 간접화법 같은 메타 서술을 피한다. “사용자가 물었다”, “설명했다” 같은 표현을 쓰지 않는다.
- 사용자가 바로 듣는 최종 브리핑처럼 직접 서술한다.
- 간단한 코드 수정은 2~3문장으로 요약한다.
- 중간 규모 구현 작업은 4~6문장으로 과정과 결정사항을 포함한다.
- 복잡한 구조 변경이나 디버깅은 7~10문장으로 과정, 결정사항, 트레이드오프를 포함한다.
- 개발 작업이 아닌 조사, 문서 작성, 정보 정리, 브리핑은 수정 파일 수가 아니라 응답의 길이와 정보량에 따라 요약 분량을 자연스럽게 조절한다.
- 오류나 검증하지 못한 부분이 있으면 반드시 포함한다.
- 지침 파일에서 TTS 재생을 직접 호출하지 않는다. 음성 재생은 Stop hook이 담당한다.

## 경로 정확성

지침 블록에는 실제 임시 파일 경로와 실제 보관 폴더 경로를 적어야 한다. 훅이 `TTS-Summary/txt`에 보관하는데, 예전 평면 보관 경로나 단일 `tts-summary.txt` 보관 경로가 글로벌 지침에 남아 있으면 안 된다.
