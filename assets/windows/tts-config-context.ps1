#
# UserPromptSubmit hook - TTS 설정의 사용 여부와 상세 정도를 에이전트에게 한 줄로 알린다.
# 재생은 Stop hook이 담당하고, 이 훅은 "요약을 쓸지, 얼마나 자세히 쓸지"만 전달한다.
# 설정을 바꾸면 다음 턴부터 바로 반영된다.
#
# 이식 방법: $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다(.claude / .codex / .gemini).
#

$ErrorActionPreference = "SilentlyContinue"

$AgentDirName = ".claude"   # <-- 이식 시 이 한 줄만 변경

# 훅 출력은 UTF-8로 읽히므로 콘솔 출력 인코딩을 맞춘다(한글 깨짐 방지).
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

try {
    . (Join-Path $PSScriptRoot "tts-config.ps1")
    $AgentDir = "$env:USERPROFILE\$AgentDirName"
    $config = Get-TtsConfig $AgentDir

    if (-not (Test-TtsEnabled $config)) {
        Write-Output "[tts-config] TTS 음성 요약 끔. tts-summary.txt를 쓰지 않는다."
        exit 0
    }

    switch ($config.verbosity.Trim()) {
        "1"     { $detail = "1단계(1~2문장, 결과만)" }
        "3"     { $detail = "3단계(7문장 이상, 근거·트레이드오프·후속 과제 포함)" }
        default { $detail = "2단계(3~6문장, 과정과 결정 포함)" }
    }
    Write-Output "[tts-config] TTS 음성 요약 켬, 상세 정도 $detail. tts-summary.txt를 쓴다."
} catch {}

exit 0
