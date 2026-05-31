# macOS 구성 참고

## 권장 폴더 구조

각 에이전트 홈 안에 shell hook을 둔다.

- Claude: `.claude/hooks`
- Codex: `.codex/hooks-macos`
- Gemini/Antigravity: `.gemini/hooks`

각 훅은 자기 에이전트 홈의 `tts-summary.txt`를 읽고, 같은 홈 아래 보관 폴더에 TXT와 WAV를 저장해야 한다.

## 음성

가장 단순하고 이식성 높은 macOS provider는 `say`다.

검증된 macOS 구성의 예시는 다음과 같다.

- Claude 한국어: `Jian (Premium)`
- Codex 한국어: `Minsu (Enhanced)`
- Gemini/Antigravity 한국어: `Yuna (Premium)`
- 빠른 재생 공통 속도: 약 `400` WPM

사용 가능한 음성 이름은 macOS 버전과 다운로드된 음성에 따라 달라진다. 항상 다음 명령으로 확인한다.

```bash
say -v '?'
```

## 오디오 파일

`say -o`로 오디오 파일을 생성하고, 로컬 워크플로우가 WAV 보관을 기대하면 WAV로 변환한다. `say`의 rate만으로 충분히 빠르지 않으면 `ffmpeg` 후처리로 속도를 조정한다.

## 정리 규칙

macOS에서도 Windows와 같은 정리 규칙을 적용한다.

- TXT는 `TTS-Summary/txt`에 보관한다.
- WAV는 `TTS-Summary/wav`에 보관한다.
- 각각 최신 10개만 남긴다.
