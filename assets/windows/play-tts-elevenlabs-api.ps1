#
# ElevenLabs API TTS provider (Windows) - OS 내장 SAPI 대신 고품질 ElevenLabs 음색을 쓰고 싶을 때 사용한다.
# Claude·Codex·Gemini/Antigravity 어디서나 tts-provider.txt에 "elevenlabs-api"를 적으면 stop-tts.ps1이 호출한다.
# speech-toolkit/TTS/elevenlabs_tts.py를 호출해 MP3를 만들고, ffmpeg로 PCM WAV로 변환(속도 보정 동시 적용)한 뒤
# SAPI provider와 같은 "Saved to:" 형식을 출력하고 재생한다.
#
# 전제: 환경 변수 ELEVENLABS_API_KEY 설정(유료 API), $ConverterScript 경로 존재,
#       ffmpeg 필수(MP3 -> WAV 변환. System.Media.SoundPlayer는 WAV만 재생).
# 이식 방법: $AgentDirName, $ConverterScript 두 곳을 환경에 맞게 바꾼다.
# 음성은 에이전트 홈의 tts-voice-elevenlabs.txt로 제어한다(없으면 param 기본값 사용).
# 검증된 구성: 모델 eleven_turbo_v2_5(짧은 요약 기준 v3보다 합성 지연이 짧음), 음성 Yuna(한국어).
# 요약 언어를 바꿨다면 그 언어에 맞는 음성 이름으로 바꾼다(모델은 다국어 지원).
#

param(
    [Parameter(Mandatory = $true)]
    [string]$Text,

    [Parameter(Mandatory = $false)]
    [string]$Voice = "Yuna",

    # 빈 문자열이면 elevenlabs_tts.py 기본값(eleven_v3)을 사용한다.
    # 턴 요약은 짧은 문장이라 v3(약 5초)보다 빠른 turbo(약 2초)를 기본으로 둔다.
    [Parameter(Mandatory = $false)]
    [string]$Model = "eleven_turbo_v2_5"
)

$ErrorActionPreference = "Stop"

$AgentDirName    = ".codex"   # <-- 이식 시 변경 (.claude / .codex / .gemini)
$ConverterScript = "<SPEECH_TOOLKIT_DIR>\TTS\elevenlabs_tts.py"  # <-- speech-toolkit 패키지( https://github.com/Engccer/speech-toolkit )의 elevenlabs_tts.py 경로로 바꾼다(이 provider 전용 외부 의존)

$AgentDir  = "$env:USERPROFILE\$AgentDirName"
$AudioDir  = "$AgentDir\TTS-Summary\wav"
$TempDir   = "$AgentDir\TTS-Summary\tmp"
$LogDir    = "$AgentDir\log"
$LogFile   = "$LogDir\elevenlabs-api-tts.log"
$RateFile  = "$AgentDir\tts-speech-rate.txt"
$VoiceFile = "$AgentDir\tts-voice-elevenlabs.txt"
$MaxAudioFiles = 10

# CLI 인자가 기본값 그대로면 에이전트 홈의 설정 파일이 우선한다.
if ($Voice -eq "Yuna" -and (Test-Path $VoiceFile)) {
    $ConfiguredVoice = (Get-Content $VoiceFile -Raw -Encoding UTF8).Trim()
    if ($ConfiguredVoice) { $Voice = $ConfiguredVoice }
}

New-Item -ItemType Directory -Path $AudioDir, $TempDir, $LogDir -Force | Out-Null

function Write-Log {
    param([string]$Message)
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

# tts-speech-rate.txt(-10~10)를 ffmpeg atempo 배율(0.5~2.0)로 매핑한다(Gemini provider와 동일 규약).
function Get-TempoMultiplier {
    if (-not (Test-Path $RateFile)) { return 1.0 }
    $rawRate = (Get-Content -LiteralPath $RateFile -Raw -Encoding UTF8).Trim()
    $rateValue = 0
    if (-not [int]::TryParse($rawRate, [ref]$rateValue)) { return 1.0 }
    if ($rateValue -ge 0) {
        $tempo = 1.0 + ([Math]::Min($rateValue, 10) * 0.1)
    } else {
        $tempo = 1.0 + ([Math]::Max($rateValue, -10) * 0.05)
    }
    if ($tempo -lt 0.5) { return 0.5 }
    if ($tempo -gt 2.0) { return 2.0 }
    return $tempo
}

try {
    if (-not $env:ELEVENLABS_API_KEY) { throw "ELEVENLABS_API_KEY is not set." }
    if (-not (Test-Path $ConverterScript)) { throw "Converter script not found: $ConverterScript" }

    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $ffmpeg) { throw "ffmpeg not found; required to convert ElevenLabs MP3 to a playable WAV." }

    $CleanText = ($Text -replace '\s+', ' ').Trim()
    if (-not $CleanText) { throw "Text is empty after normalization." }

    $Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-ffff'
    $InputFile = Join-Path $TempDir "el-$Timestamp.txt"
    $ExpectedMp3 = Join-Path $TempDir "el-$Timestamp`_elevenlabs.mp3"
    $AudioFile = Join-Path $AudioDir "tts-$Timestamp.wav"

    Set-Content -LiteralPath $InputFile -Value $CleanText -Encoding UTF8
    $env:PYTHONUTF8 = "1"

    Remove-Item -LiteralPath $ExpectedMp3 -Force -ErrorAction SilentlyContinue

    # --single: 요약은 항상 단일 화자이므로 다중 화자 자동 감지를 끈다.
    $PyArgs = @($ConverterScript, $InputFile, "--single", "--voice", $Voice)
    if ($Model) { $PyArgs += @("--model", $Model) }

    Write-Log "Starting ElevenLabs API TTS voice=$Voice model=$Model chars=$($CleanText.Length)"
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $Result = & python @PyArgs 2>&1
    $ExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorActionPreference
    ($Result | Out-String).Trim() | Out-File -FilePath $LogFile -Append -Encoding UTF8

    if (-not (Test-Path $ExpectedMp3)) { throw "Expected MP3 output was not created (exitCode=$ExitCode)." }

    # MP3 -> PCM WAV 변환. 속도 보정(atempo)도 같은 패스에서 적용한다.
    $tempo = Get-TempoMultiplier
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    $tempoText = $tempo.ToString("0.###", $culture)

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    if ([Math]::Abs($tempo - 1.0) -lt 0.01) {
        Write-Log "Converting MP3 to WAV source=$ExpectedMp3"
        $ConvResult = & $ffmpeg.Source -y -i $ExpectedMp3 -ar 44100 -ac 2 -c:a pcm_s16le $AudioFile 2>&1
    } else {
        Write-Log "Converting MP3 to WAV with tempo=$tempoText source=$ExpectedMp3"
        $ConvResult = & $ffmpeg.Source -y -i $ExpectedMp3 -filter:a "atempo=$tempoText" -ar 44100 -ac 2 -c:a pcm_s16le $AudioFile 2>&1
    }
    $ConvExit = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorActionPreference
    ($ConvResult | Out-String).Trim() | Out-File -FilePath $LogFile -Append -Encoding UTF8

    if ($ConvExit -ne 0 -or -not (Test-Path $AudioFile)) { throw "ffmpeg MP3->WAV conversion failed (exitCode=$ConvExit)." }

    Remove-Item -LiteralPath $InputFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $ExpectedMp3 -Force -ErrorAction SilentlyContinue

    Write-Host "[OK] Saved to: $AudioFile"
    Write-Host "[VOICE] Voice used: $Voice (ElevenLabs API TTS / $(if ($Model) { $Model } else { 'eleven_v3' }))"
    Write-Log "Saved to: $AudioFile"

    # WAV만 생성하고 재생은 생략하려면 환경 변수 TTS_NO_PLAY=1 (SAPI provider와 동일 규약).
    # 합성은 성공했으므로 재생 실패는 provider 실패로 치지 않는다(폴백 재합성 방지).
    if (-not $env:TTS_NO_PLAY) {
        try {
            $player = New-Object System.Media.SoundPlayer $AudioFile
            $player.PlaySync()
            $player.Dispose()
        } catch {
            Write-Log "Playback failed (WAV archived): $_"
        }
    }
} catch {
    Write-Host "[ERROR] ElevenLabs API TTS failed: $_"
    Write-Log "ERROR: $_"
    exit 1
} finally {
    Get-ChildItem -Path $TempDir -Filter "el-*.txt" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-6) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $TempDir -Filter "el-*.mp3" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-6) } |
        Remove-Item -Force -ErrorAction SilentlyContinue

    $wavFiles = Get-ChildItem -Path $AudioDir -Filter "tts-*.wav" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
    if ($wavFiles.Count -gt $MaxAudioFiles) {
        $wavFiles | Select-Object -Skip $MaxAudioFiles | ForEach-Object {
            Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

# stop-tts.ps1이 exit code로 성공/실패를 판정하므로 성공을 명시한다.
exit 0
