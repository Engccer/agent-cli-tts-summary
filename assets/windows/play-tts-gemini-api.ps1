#
# Gemini API TTS provider (Windows) - Gemini/Antigravity가 구분되는 음색을 쓰고 싶을 때 SAPI 대신 사용한다.
# speech-toolkit/TTS/gemini_tts.py를 호출해 WAV를 만들고, SAPI provider와 같은 "Saved to:" 형식을 출력한다.
#
# 전제: 환경 변수 GEMINI_API_KEY 설정, $ConverterScript 경로 존재, (선택) ffmpeg로 속도 보정.
# 이식 방법: $AgentDirName, $ConverterScript 두 곳을 환경에 맞게 바꾼다.
# 검증된 구성: 모델 gemini-3.1-flash-tts-preview, 음성 Puck (references/windows.md 참고).
#

param(
    [Parameter(Mandatory = $true)]
    [string]$Text,

    [Parameter(Mandatory = $false)]
    [string]$Voice = "Puck",

    [Parameter(Mandatory = $false)]
    [string]$Model = "gemini-3.1-flash-tts-preview",

    [Parameter(Mandatory = $false)]
    [string]$LanguageCode = "ko-KR"
)

$ErrorActionPreference = "Stop"

$AgentDirName    = ".gemini"   # <-- 이식 시 변경
$ConverterScript = "<SPEECH_TOOLKIT_DIR>\TTS\gemini_tts.py"  # <-- speech-toolkit 패키지( https://github.com/Engccer/speech-toolkit )의 gemini_tts.py 경로로 바꾼다(이 provider 전용 외부 의존)

$AgentDir  = "$env:USERPROFILE\$AgentDirName"
$AudioDir  = "$AgentDir\TTS-Summary\wav"
$TempDir   = "$AgentDir\TTS-Summary\tmp"
$LogDir    = "$AgentDir\log"
$LogFile   = "$LogDir\gemini-api-tts.log"
$RateFile  = "$AgentDir\tts-speech-rate.txt"
$MaxAudioFiles = 10

New-Item -ItemType Directory -Path $AudioDir, $TempDir, $LogDir -Force | Out-Null

function Write-Log {
    param([string]$Message)
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

# tts-speech-rate.txt(-10~10)를 ffmpeg atempo 배율(0.5~2.0)로 매핑한다.
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

function Apply-Tempo {
    param([string]$AudioFile)
    $tempo = Get-TempoMultiplier
    if ([Math]::Abs($tempo - 1.0) -lt 0.01) { return }
    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $ffmpeg) {
        Write-Log "ffmpeg not found; skipping tempo adjustment tempo=$tempo"
        return
    }
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    $tempoText = $tempo.ToString("0.###", $culture)
    $AdjustedFile = [System.IO.Path]::ChangeExtension($AudioFile, ".tempo.wav")
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $Result = & $ffmpeg.Source -y -i $AudioFile -filter:a "atempo=$tempoText" $AdjustedFile 2>&1
    $ExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorActionPreference
    ($Result | Out-String).Trim() | Out-File -FilePath $LogFile -Append -Encoding UTF8
    if ($ExitCode -eq 0 -and (Test-Path $AdjustedFile)) {
        Move-Item -LiteralPath $AdjustedFile -Destination $AudioFile -Force
    } else {
        Remove-Item -LiteralPath $AdjustedFile -Force -ErrorAction SilentlyContinue
        Write-Log "Tempo adjustment failed exitCode=$ExitCode; keeping original WAV"
    }
}

try {
    if (-not $env:GEMINI_API_KEY) { throw "GEMINI_API_KEY is not set." }
    if (-not (Test-Path $ConverterScript)) { throw "Converter script not found: $ConverterScript" }

    $CleanText = ($Text -replace '\s+', ' ').Trim()
    if (-not $CleanText) { throw "Text is empty after normalization." }

    $Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-ffff'
    $InputFile = Join-Path $TempDir "tts-$Timestamp.txt"
    $ExpectedOutput = Join-Path $TempDir "tts-$Timestamp`_gemini_tts.wav"
    $AudioFile = Join-Path $AudioDir "tts-$Timestamp.wav"

    Set-Content -LiteralPath $InputFile -Value $CleanText -Encoding UTF8
    $env:PYTHONUTF8 = "1"

    # 지정 모델이 404면 검증된 preview 모델로 폴백한다.
    $ModelsToTry = @($Model)
    if ($Model -ne "gemini-3.1-flash-tts-preview") {
        $ModelsToTry += "gemini-3.1-flash-tts-preview"
    }

    $UsedModel = ""
    foreach ($CandidateModel in $ModelsToTry) {
        Remove-Item -LiteralPath $ExpectedOutput -Force -ErrorAction SilentlyContinue
        $Args = @($ConverterScript, $InputFile, "--model", $CandidateModel, "--voice", $Voice, "--language-code", $LanguageCode)
        Write-Log "Starting Gemini API TTS model=$CandidateModel voice=$Voice language=$LanguageCode chars=$($CleanText.Length)"
        $PreviousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $Result = & python @Args 2>&1
        $ExitCode = $LASTEXITCODE
        $ErrorActionPreference = $PreviousErrorActionPreference
        ($Result | Out-String).Trim() | Out-File -FilePath $LogFile -Append -Encoding UTF8
        if (Test-Path $ExpectedOutput) {
            $UsedModel = $CandidateModel
            break
        }
        Write-Log "No WAV output from model=$CandidateModel exitCode=$ExitCode"
    }

    if (-not $UsedModel) { throw "Expected output was not created after trying: $($ModelsToTry -join ', ')" }

    Move-Item -LiteralPath $ExpectedOutput -Destination $AudioFile -Force
    Remove-Item -LiteralPath $InputFile -Force -ErrorAction SilentlyContinue
    Apply-Tempo -AudioFile $AudioFile

    Write-Host "[OK] Saved to: $AudioFile"
    Write-Host "[VOICE] Voice used: $Voice (Gemini API TTS / $UsedModel)"
    Write-Log "Saved to: $AudioFile"
} catch {
    Write-Host "[ERROR] Gemini API TTS failed: $_"
    Write-Log "ERROR: $_"
    exit 1
} finally {
    Get-ChildItem -Path $TempDir -Filter "tts-*.txt" -ErrorAction SilentlyContinue |
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
