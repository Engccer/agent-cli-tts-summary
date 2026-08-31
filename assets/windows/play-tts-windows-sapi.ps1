#
# Windows SAPI TTS provider - System.Speech로 WAV를 만들고 재생한 뒤 최신 10개만 보관한다.
# stop-tts.ps1이 호출한다. 단독 실행도 가능: .\play-tts-windows-sapi.ps1 "읽을 문장"
#
# 이식 방법: $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다.
# 음성과 속도는 TTS-Summary 폴더의 tts-config.txt에서 읽는다(voice_sapi, speed).
# 파싱은 같은 폴더의 tts-config.ps1이 담당한다.
#

param(
    [Parameter(Mandatory = $true)]
    [string]$Text,

    [Parameter(Mandatory = $false)]
    [string]$VoiceOverride
)

$AgentDirName = ".codex"   # <-- 이식 시 이 한 줄만 변경

$AgentDir  = "$env:USERPROFILE\$AgentDirName"
$AudioDir  = "$AgentDir\TTS-Summary\wav"
$MaxAudioFiles = 10

. (Join-Path $PSScriptRoot "tts-config.ps1")
$TtsConfig = Get-TtsConfig $AgentDir

if (-not (Test-Path $AudioDir)) {
    New-Item -ItemType Directory -Path $AudioDir -Force | Out-Null
}

try {
    Add-Type -AssemblyName System.Speech
} catch {
    Write-Host "[ERROR] System.Speech assembly not available" -ForegroundColor Red
    exit 1
}

$VoiceName = ""
if ($VoiceOverride) {
    $VoiceName = $VoiceOverride
} else {
    $VoiceName = "$($TtsConfig.voice_sapi)".Trim()
}

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

$rate = ConvertTo-SapiRate $TtsConfig.speed
if ($null -ne $rate) { $synth.Rate = $rate }

if ($VoiceName) {
    try {
        $synth.SelectVoice($VoiceName)
    } catch {
        Write-Host "[WARNING] Voice '$VoiceName' not found, using default" -ForegroundColor Yellow
    }
}

# SAPI가 오독하거나 멈출 수 있는 문자를 제거한다. 한글·영문은 그대로 둔다.
$Text = $Text -replace '\\', ' '
$Text = $Text -replace '[{}<>|`~^$;"''()]', ''
$Text = $Text -replace '&[a-zA-Z]+;', ''
$Text = $Text -replace '\s+', ' '
$Text = $Text.Trim()

$ActualVoice = $synth.Voice.Name
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-ffff'
$AudioFile = "$AudioDir\tts-$Timestamp.wav"

$player = $null
try {
    $synth.SetOutputToWaveFile($AudioFile)
    $synth.Speak($Text)

    Write-Host "[OK] Saved to: $AudioFile" -ForegroundColor Green
    Write-Host "[VOICE] Voice used: $ActualVoice (Windows SAPI)" -ForegroundColor Green

    # WAV만 생성하고 재생은 생략하려면 환경 변수 TTS_NO_PLAY=1
    if (-not $env:TTS_NO_PLAY) {
        try {
            $player = New-Object System.Media.SoundPlayer $AudioFile
            $player.PlaySync()
        } catch {
            Write-Host "[WARNING] Could not play audio (SoundPlayer unavailable)" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "[ERROR] Error synthesizing speech: $_" -ForegroundColor Red
    exit 1
} finally {
    if ($synth) { $synth.Dispose() }
    if ($player) { $player.Dispose() }

    $wavFiles = Get-ChildItem -Path $AudioDir -Filter "tts-*.wav" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if ($wavFiles.Count -gt $MaxAudioFiles) {
        $wavFiles | Select-Object -Skip $MaxAudioFiles | ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }
    }
}

# stop-tts.ps1이 exit code로 성공/실패를 판정하므로 성공을 명시한다.
exit 0
