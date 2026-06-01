#
# Stop hook (Windows) - 에이전트가 쓴 tts-summary.txt를 읽어 음성으로 재생하고 보관한다.
#
# 이식 방법: 아래 $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다.
#   Claude -> ".claude" / Codex -> ".codex" / Gemini·Antigravity -> ".gemini"
# 재생 provider도 한 곳에서 고른다($TtsScript). 기본은 같은 폴더의 SAPI provider.
#
# 설계 원칙(references/architecture.md): 본문 응답 중에는 TTS를 호출하지 않고,
# 재생은 전적으로 이 Stop hook이 담당한다. 실패해도 CLI 턴을 깨지 않도록 조용히 종료한다.
#

$ErrorActionPreference = "SilentlyContinue"

$AgentDirName = ".codex"   # <-- 이식 시 이 한 줄만 변경

$AgentDir          = "$env:USERPROFILE\$AgentDirName"
$SummaryFile       = "$AgentDir\tts-summary.txt"
$SummaryArchiveDir = "$AgentDir\TTS-Summary\txt"
$VoiceFile         = "$AgentDir\tts-voice-sapi.txt"
$LogFile           = "$AgentDir\log\stop-tts.log"
$RecentPlayFile    = "$AgentDir\.tmp\last-tts-summary-played"
$FallbackSound     = "$AgentDir\hook-sounds\stop-bell.wav"   # 없으면 fallback 알림음 생략
$TtsScript         = "$AgentDir\hooks-windows\play-tts-windows-sapi.ps1"
$RecentPlaySuppressSeconds = 180
$MaxSummaryFiles   = 10

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

if (-not (Test-Path $SummaryFile)) {
    if (Test-RecentTtsPlay) { exit 0 }
    Play-StopFallback
    exit 0
}

$Summary = (Get-Content $SummaryFile -Raw -Encoding UTF8).Trim()
Remove-Item $SummaryFile -Force
Save-SummaryArchive $Summary

if (-not $Summary) {
    if (Test-RecentTtsPlay) { exit 0 }
    Play-StopFallback
    exit 0
}

if (Test-Path $TtsScript) {
    $VoiceOverride = ""
    if (Test-Path $VoiceFile) {
        $VoiceOverride = (Get-Content $VoiceFile -Raw -Encoding UTF8).Trim()
    }
    try {
        New-Item -ItemType Directory -Path (Split-Path -Parent $LogFile) -Force | Out-Null
        if ($VoiceOverride) {
            & $TtsScript $Summary $VoiceOverride *> $LogFile
        } else {
            & $TtsScript $Summary *> $LogFile
        }
        Mark-TtsPlay
    } catch {}
} else {
    Play-StopFallback
    exit 0
}
