#
# Azure AI Speech TTS provider (Windows) - OS 내장 SAPI 대신 Azure 한국어 neural 음색을 쓸 때 사용한다.
# 설정 파일의 provider에 "azure-api"를 적으면 stop-tts.ps1이 호출한다.
# 이 스킬에 동봉된 assets/tts/azure_tts.py를 호출해 WAV를 만들고, SAPI provider와 같은 "Saved to:" 형식을 출력한다.
#
# 전제: 환경 변수 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION 설정. 표준 라이브러리만 쓰므로 pip 패키지는 필요 없다.
# 속도는 2배까지 SSML <prosody rate>로 합성 단계에서 넣고, 2배를 넘는 부분(speed 7.5 초과)만 ffmpeg atempo로 보탠다.
# ffmpeg가 없으면 2배로 재생한다.
# 이식 방법: $AgentDirName, $ConverterScript 두 곳을 환경에 맞게 바꾼다.
# 음성·언어·속도는 TTS-Summary 폴더의 tts-config.txt에서 읽는다(voice_azure, language_code, speed).
#

param(
    [Parameter(Mandatory = $true)]
    [string]$Text,

    [Parameter(Mandatory = $false)]
    [string]$Voice = "ko-KR-SunHiNeural",

    [Parameter(Mandatory = $false)]
    [string]$LanguageCode = "ko-KR"
)

$ErrorActionPreference = "Stop"

$AgentDirName    = ".codex"   # <-- 이식 시 변경 (.claude / .codex / .gemini)
$ConverterScript = "<SKILL_DIR>\assets\tts\azure_tts.py"  # <-- 이 스킬 설치 폴더에 동봉된 azure_tts.py의 절대 경로로 바꾼다(예: %USERPROFILE%\.claude\skills\agent-cli-tts-summary\assets\tts\azure_tts.py)

$AgentDir  = "$env:USERPROFILE\$AgentDirName"
$AudioDir  = "$AgentDir\TTS-Summary\wav"
$TempDir   = "$AgentDir\TTS-Summary\tmp"
$LogDir    = "$AgentDir\log"
$LogFile   = "$LogDir\azure-api-tts.log"
. (Join-Path $PSScriptRoot "tts-config.ps1")
$TtsConfig = Get-TtsConfig $AgentDir
$MaxAudioFiles = 10

# CLI 인자가 기본값 그대로면 설정 파일 값이 우선한다.
if ($Voice -eq "ko-KR-SunHiNeural") {
    $ConfiguredVoice = "$($TtsConfig.voice_azure)".Trim()
    if ($ConfiguredVoice) { $Voice = $ConfiguredVoice }
}
if ($LanguageCode -eq "ko-KR") {
    $ConfiguredLanguage = "$($TtsConfig.language_code)".Trim()
    if ($ConfiguredLanguage) { $LanguageCode = $ConfiguredLanguage }
}

New-Item -ItemType Directory -Path $AudioDir, $TempDir, $LogDir -Force | Out-Null

function Write-Log {
    param([string]$Message)
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

# Azure prosody rate가 받지 못하는 2배 초과분을 ffmpeg atempo로 보탠다.
# 2배까지는 합성 단계에서, 그 위는 후처리로 나눠 다른 API provider와 같은 배율 곡선(speed 10 = 4배)을 맞춘다.
function Apply-ResidualTempo {
    param([string]$AudioFile, [double]$Tempo)
    if ([Math]::Abs($Tempo - 1.0) -lt 0.01) { return }
    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $ffmpeg) {
        Write-Log "ffmpeg not found; skipping residual tempo=$Tempo (playing at Azure max 2.0x)"
        return
    }
    $tempoText = Get-AtempoFilter $Tempo
    $AdjustedFile = [System.IO.Path]::ChangeExtension($AudioFile, ".tempo.wav")
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $Result = & $ffmpeg.Source -y -i $AudioFile -filter:a "$tempoText" $AdjustedFile 2>&1
    $ExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorActionPreference
    ($Result | Out-String).Trim() | Out-File -FilePath $LogFile -Append -Encoding UTF8
    if ($ExitCode -eq 0 -and (Test-Path $AdjustedFile)) {
        Move-Item -LiteralPath $AdjustedFile -Destination $AudioFile -Force
    } else {
        Remove-Item -LiteralPath $AdjustedFile -Force -ErrorAction SilentlyContinue
        Write-Log "Residual tempo failed exitCode=$ExitCode; keeping 2.0x WAV"
    }
}

try {
    # 키를 저장한 뒤 재시작하지 않은 세션은 프로세스 환경에 값이 없으므로 사용자 환경 변수에서 읽는다.
    foreach ($n in "AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION") {
        if (-not [Environment]::GetEnvironmentVariable($n)) {
            [Environment]::SetEnvironmentVariable($n, [Environment]::GetEnvironmentVariable($n, "User"))
        }
    }
    if (-not $env:AZURE_SPEECH_KEY) { throw "AZURE_SPEECH_KEY is not set." }
    if (-not $env:AZURE_SPEECH_REGION) { throw "AZURE_SPEECH_REGION is not set." }
    if (-not (Test-Path $ConverterScript)) { throw "Converter script not found: $ConverterScript" }

    $CleanText = ($Text -replace '\s+', ' ').Trim()
    if (-not $CleanText) { throw "Text is empty after normalization." }

    $Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-ffff'
    $InputFile = Join-Path $TempDir "tts-$Timestamp.txt"
    $ExpectedOutput = Join-Path $TempDir "tts-$Timestamp`_azure_tts.wav"
    $AudioFile = Join-Path $AudioDir "tts-$Timestamp.wav"

    Set-Content -LiteralPath $InputFile -Value $CleanText -Encoding UTF8
    $env:PYTHONUTF8 = "1"

    Remove-Item -LiteralPath $ExpectedOutput -Force -ErrorAction SilentlyContinue

    # 속도는 2배까지 SSML rate로 합성 단계에서 넣고, 넘는 부분만 ffmpeg로 보탠다.
    $Tempo = ConvertTo-TtsTempo $TtsConfig.speed
    $SynthTempo = [Math]::Min($Tempo, 2.0)
    $ResidualTempo = $Tempo / $SynthTempo
    $TempoText = $SynthTempo.ToString([System.Globalization.CultureInfo]::InvariantCulture)

    $PyArgs = @($ConverterScript, $InputFile, "--voice", $Voice, "--language-code", $LanguageCode, "--tempo", $TempoText)
    Write-Log "Starting Azure API TTS voice=$Voice language=$LanguageCode tempo=$Tempo synth=$TempoText chars=$($CleanText.Length)"

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $Result = & python @PyArgs 2>&1
    $ExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorActionPreference
    ($Result | Out-String).Trim() | Out-File -FilePath $LogFile -Append -Encoding UTF8

    if (-not (Test-Path $ExpectedOutput)) { throw "Expected output was not created (exitCode=$ExitCode)." }

    Move-Item -LiteralPath $ExpectedOutput -Destination $AudioFile -Force
    Remove-Item -LiteralPath $InputFile -Force -ErrorAction SilentlyContinue
    Apply-ResidualTempo -AudioFile $AudioFile -Tempo $ResidualTempo

    Write-Host "[OK] Saved to: $AudioFile"
    Write-Host "[VOICE] Voice used: $Voice (Azure API TTS)"
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
    Write-Host "[ERROR] Azure API TTS failed: $_"
    Write-Log "ERROR: $_"
    exit 1
} finally {
    Get-ChildItem -Path $TempDir -Include "tts-*.txt", "tts-*_azure_tts.wav" -File -Recurse -ErrorAction SilentlyContinue |
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
