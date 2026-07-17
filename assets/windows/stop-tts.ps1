#
# Stop hook (Windows) - 에이전트가 쓴 tts-summary.txt를 읽어 음성으로 재생하고 보관한다.
#
# 이식 방법: 아래 $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다.
#   Claude -> ".claude" / Codex -> ".codex" / Gemini·Antigravity -> ".gemini"
# 재생 provider는 에이전트 홈의 tts-provider.txt로 고른다(모든 에이전트 공통):
#   windows-sapi(기본) / gemini-api / elevenlabs-api
# provider 스크립트는 이 파일과 같은 폴더에서 찾고, API provider가 실패하면
# SAPI provider로 런타임 폴백해 요약이 항상 들리게 한다.
#
# 설계 원칙(references/architecture.md): 본문 응답 중에는 TTS를 호출하지 않고,
# 재생은 전적으로 이 Stop hook이 담당한다. 실패해도 CLI 턴을 깨지 않도록 조용히 종료한다.
#
# 요약 누락 가드: 에이전트가 tts-summary.txt를 쓰지 않고 턴을 끝내면, 아직 한 번도
# 재요청하지 않은 경우에 한해 exit 2로 응답을 차단하고 요약 작성을 요구한다. Stop hook
# payload(stdin)의 stop_hook_active가 true면 이미 한 번 재요청한 것이므로 무한루프를 피해 통과한다.
#

$ErrorActionPreference = "SilentlyContinue"

$AgentDirName = ".codex"   # <-- 이식 시 이 한 줄만 변경

$AgentDir          = "$env:USERPROFILE\$AgentDirName"
$SummaryFile       = "$AgentDir\tts-summary.txt"
$SummaryArchiveDir = "$AgentDir\TTS-Summary\txt"
$ProviderFile      = "$AgentDir\tts-provider.txt"
$LogFile           = "$AgentDir\log\stop-tts.log"
$RecentPlayFile    = "$AgentDir\.tmp\last-tts-summary-played"
$FallbackSound     = "$AgentDir\hook-sounds\stop-bell.wav"   # 없으면 fallback 알림음 생략
$RecentPlaySuppressSeconds = 180
$MaxSummaryFiles   = 10

# --- provider 선택 ---
# tts-provider.txt 값으로 provider 스크립트를 고른다. 파일이 없거나 값이 인식되지
# 않으면 SAPI(OS 내장, 자체 완결)를 쓴다. 각 provider는 자기 음성 파일을 스스로 읽으므로
# (tts-voice-sapi.txt / tts-voice-gemini.txt / tts-voice-elevenlabs.txt) 여기서는 텍스트만 넘긴다.
$SapiScript = Join-Path $PSScriptRoot "play-tts-windows-sapi.ps1"
$Provider = ""
if (Test-Path $ProviderFile) {
    $Provider = (Get-Content $ProviderFile -Raw -Encoding UTF8).Trim().ToLowerInvariant()
}
switch ($Provider) {
    "gemini-api"     { $TtsScript = Join-Path $PSScriptRoot "play-tts-gemini-api.ps1" }
    "elevenlabs-api" { $TtsScript = Join-Path $PSScriptRoot "play-tts-elevenlabs-api.ps1" }
    default          { $TtsScript = $SapiScript }
}
if (-not (Test-Path $TtsScript)) { $TtsScript = $SapiScript }

function Play-StopFallback {
    if (-not (Test-Path $FallbackSound)) { return }
    try {
        $player = New-Object Media.SoundPlayer $FallbackSound
        $player.PlaySync()
        $player.Dispose()
    } catch {}
}

# 같은 턴에서 이미 재생했으면 fallback 알림음 중복을 막는다.
function Test-RecentTtsPlay {
    try {
        if (-not (Test-Path $RecentPlayFile)) { return $false }
        $lastWrite = (Get-Item $RecentPlayFile).LastWriteTime
        return ((Get-Date) - $lastWrite).TotalSeconds -lt $RecentPlaySuppressSeconds
    } catch { return $false }
}

function Mark-TtsPlay {
    try {
        New-Item -ItemType Directory -Path (Split-Path -Parent $RecentPlayFile) -Force | Out-Null
        Set-Content -LiteralPath $RecentPlayFile -Value (Get-Date -Format o) -Encoding UTF8
    } catch {}
}

function Save-SummaryArchive {
    param([string]$SummaryText)
    if (-not $SummaryText) { return }
    try {
        New-Item -ItemType Directory -Path $SummaryArchiveDir -Force | Out-Null
        $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-ffff'
        $archiveFile = Join-Path $SummaryArchiveDir "summary-$timestamp.txt"
        Set-Content -LiteralPath $archiveFile -Value $SummaryText -Encoding UTF8

        $summaryFiles = Get-ChildItem -Path $SummaryArchiveDir -Filter "summary-*.txt" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending
        if ($summaryFiles.Count -gt $MaxSummaryFiles) {
            $summaryFiles | Select-Object -Skip $MaxSummaryFiles | ForEach-Object {
                Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

# --- 요약 누락 가드 ---
# Stop hook payload(stdin)의 stop_hook_active를 읽어 무한루프를 방지한다.
$HookInput = ""
try { $HookInput = [Console]::In.ReadToEnd() } catch {}
$StopActive = $HookInput -match '"stop_hook_active"\s*:\s*true'

# 요약 언어는 글로벌 지침의 TTS 요약 규칙이 정하므로 여기서는 특정 언어를 강제하지 않는다.
$MissingSummaryMessage = "TTS 요약 누락: 글로벌 지침(CLAUDE.md/AGENTS.md/GEMINI.md)의 TTS 요약 규칙에 따라(지정된 요약 언어 포함) 이번 응답의 요약을 $SummaryFile 에 파일 편집 도구로 작성한 뒤 응답을 마치세요."

if (-not (Test-Path $SummaryFile)) {
    if (-not $StopActive) {
        [Console]::Error.WriteLine($MissingSummaryMessage)
        exit 2
    }
    if (Test-RecentTtsPlay) { exit 0 }
    Play-StopFallback
    exit 0
}

$Summary = (Get-Content $SummaryFile -Raw -Encoding UTF8).Trim()
Remove-Item $SummaryFile -Force
Save-SummaryArchive $Summary

if (-not $Summary) {
    if (-not $StopActive) {
        [Console]::Error.WriteLine($MissingSummaryMessage)
        exit 2
    }
    if (Test-RecentTtsPlay) { exit 0 }
    Play-StopFallback
    exit 0
}

if (Test-Path $TtsScript) {
    try {
        New-Item -ItemType Directory -Path (Split-Path -Parent $LogFile) -Force | Out-Null
        & $TtsScript -Text $Summary *> $LogFile
        # provider 스크립트는 성공 시 exit 0, 실패 시 exit 1을 낸다. API provider가
        # 실패하면(키 누락, 네트워크 오류 등) SAPI로 폴백해 요약이 항상 들리게 한다.
        if ($LASTEXITCODE -ne 0 -and $TtsScript -ne $SapiScript -and (Test-Path $SapiScript)) {
            & $SapiScript -Text $Summary *>> $LogFile
        }
        Mark-TtsPlay
    } catch {}
} else {
    Play-StopFallback
}

# 재생까지 실패해도 CLI 턴을 깨지 않도록 훅 자체는 항상 성공으로 끝낸다.
exit 0
