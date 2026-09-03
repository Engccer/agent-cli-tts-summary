#
# play-tts-briefing.ps1 (Windows) - 긴 작업의 중간 phase 보고와 질문 선택지 안내를 SAPI로 재생한다.
# 훅이나 에이전트를 붙잡지 않도록, 실제 발화는 숨김 분리 프로세스(자기 자신을 -Speak로 재실행)가 맡는다.
#
# 사용법: powershell.exe -NoProfile -ExecutionPolicy Bypass -File play-tts-briefing.ps1 "보고문"
#        -TextFile <경로>  파일 내용을 읽어 발화(읽은 뒤 파일은 지운다)
#        -Speak -Rate <n> -Voice <이름>  내부용. 분리 프로세스가 설정 파일 없이 동기 발화한다
#                          (WMI로 띄운 프로세스는 부모의 환경 변수를 물려받지 않아 설정 경로를 알 수 없다.
#                          ask-question-tts.ps1도 이 형태로 호출한다)
# 검증: BRIEFING_TTS_DRYRUN=1이면 재생하지 않고 voice/rate/text를 출력한다.
#
# 음성 사용 여부(enabled), 응답 완료 전 발화 여부(interim), SAPI 음성(voice_sapi), 속도(speed)는
# TTS-Summary\tts-config.txt 하나에서 읽는다. 파싱은 같은 폴더의 tts-config.ps1이 담당한다.
#
# 이식 방법: $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다(.claude / .codex / .gemini).
#

param(
    [Parameter(Position = 0)]
    [string]$Text,
    [string]$TextFile,
    [switch]$Speak,
    [string]$Rate,
    [string]$Voice
)

$ErrorActionPreference = "SilentlyContinue"

$AgentDirName = ".claude"   # <-- 이식 시 이 한 줄만 변경

$AgentDir = "$env:USERPROFILE\$AgentDirName"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

if (-not $Text -and $TextFile -and (Test-Path -LiteralPath $TextFile)) {
    $Text = Get-Content -LiteralPath $TextFile -Raw -Encoding UTF8
    Remove-Item -LiteralPath $TextFile -Force
}
if (-not $Text) { exit 0 }

if ($Speak) {
    # 분리 프로세스: 부모가 이미 설정을 확인했고 음성·속도를 인자로 넘겼다.
    $rate = $null
    $parsed = 0
    if ([int]::TryParse("$Rate", [ref]$parsed)) { $rate = $parsed }
    $voice = "$Voice".Trim()
} else {
    . (Join-Path $PSScriptRoot "tts-config.ps1")
    $config = Get-TtsConfig $AgentDir
    if (-not (Test-TtsEnabled $config)) { exit 0 }
    if (-not (Test-TtsInterimEnabled $config)) { exit 0 }
    $rate = ConvertTo-SapiRate $config.speed
    $voice = "$($config.voice_sapi)".Trim()
}

# SAPI가 오독하거나 멈출 수 있는 문자를 제거한다. 한글·영문은 그대로 둔다.
$Text = $Text -replace '\\', ' '
$Text = $Text -replace '[{}<>|`~^$;"''()]', ''
$Text = $Text -replace '\s+', ' '
$Text = $Text.Trim()
if (-not $Text) { exit 0 }

if ($env:BRIEFING_TTS_DRYRUN -eq "1") {
    Write-Output "voice=$voice"
    Write-Output "rate=$rate"
    Write-Output "text=$Text"
    exit 0
}

if ($Speak) {
    try {
        Add-Type -AssemblyName System.Speech
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
        if ($null -ne $rate) { $synth.Rate = $rate }
        if ($voice) { try { $synth.SelectVoice($voice) } catch {} }
        $synth.Speak($Text)
        $synth.Dispose()
    } catch {}
    exit 0
}

# 분리 프로세스로 숨김 발화. 텍스트는 임시 파일로 넘겨 따옴표·특수문자 문제를 피한다.
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("tts-briefing-" + [System.IO.Path]::GetRandomFileName() + ".txt")
[System.IO.File]::WriteAllText($tmp, $Text, (New-Object System.Text.UTF8Encoding $false))
$self = $MyInvocation.MyCommand.Path
$cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$self`" -TextFile `"$tmp`" -Speak -Rate `"$rate`" -Voice `"$voice`""
$startup = ([wmiclass]"Win32_ProcessStartup").CreateInstance()
$startup.ShowWindow = 0
$result = ([wmiclass]"Win32_Process").Create($cmd, $null, $startup)
# 분리 프로세스가 뜨지 못하면 그 프로세스가 지울 임시 파일을 여기서 지운다.
if (-not $result -or $result.ReturnValue -ne 0) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }

exit 0
