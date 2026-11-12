#
# 직전 요약 음성 파일을 한 번 더 재생한다(Windows). 슬래시 명령(/tts-replay)이 이 스크립트를 부른다.
# 새로 합성하지 않고 TTS-Summary\wav에 보관된 가장 최근 WAV를 그대로 튼다(API provider여도 비용 없음).
# 설정의 enabled가 off여도 재생한다. 사용자가 직접 요청한 재생이기 때문이다.
#
# 이 턴의 요약 재생 억제: 재생 뒤에도 이 턴은 Stop hook을 지나므로, 그대로 두면 모델이 쓴
# "다시 재생했습니다" 요약이 새로 합성·재생되어 재생 중인 음성 위에 겹치고, 보관함의 "직전" 자리를
# 그 한 줄이 차지해 다음 /tts-replay가 엉뚱한 파일을 튼다. 그래서 이 턴의 요약 파일을 공백만 담아
# 미리 써 둔다. stop-tts.ps1은 공백뿐인 요약 파일을 "이 턴은 재생 없음"으로 보고 보관 없이 조용히
# 지운다. 슬래시 명령 스킬은 모델에게 이 턴에 요약을 쓰지 말라고 지시한다.
# 세션 음소거(TTS_SUMMARY=off) 세션에서는 요약 파일에 손대지 않는다(남아 있는 파일은 다른 세션 것).
#
# 재생은 숨김 분리 프로세스(stop-tts-wrapper.ps1과 같은 play-tts-queued.ps1)가 맡아 `!` 줄이 곧바로 돌아온다.
# 검증: TTS_REPLAY_DRYRUN=1이면 재생하지 않고 file=<경로>를 출력한다.
#
# 이식 방법: $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다(.claude / .codex / .gemini).
#

param(
    # 이 대화 세션의 식별자(선택). Claude 슬래시 명령은 ${CLAUDE_SESSION_ID}를 넘긴다.
    [Parameter(Position = 0)]
    [string]$SessionId
)

$ErrorActionPreference = "SilentlyContinue"

$AgentDirName = ".claude"   # <-- 이식 시 이 한 줄만 변경

$AgentDir    = "$env:USERPROFILE\$AgentDirName"
$WavDir      = "$AgentDir\TTS-Summary\wav"
$SummaryFile = "$AgentDir\tts-summary.txt"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

. (Join-Path $PSScriptRoot "tts-config.ps1")

# 공백 억제 파일은 세션 식별자를 알면 세션 전용 요약 파일에, 모르면 공용 파일에 쓴다.
# Stop hook은 세션 전용 파일이 없을 때 공용 파일을 보므로 어느 쪽이든 이 턴의 재생을 막는다.
if ($SessionId -notmatch '\A[A-Za-z0-9_-]{1,128}\z') { $SessionId = Get-TtsSessionId "" $AgentDirName }
$SessionSummaryFile = Get-TtsSessionSummaryFile $AgentDir $SessionId
if ($SessionSummaryFile) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $SessionSummaryFile) -Force | Out-Null
    $SummaryFile = $SessionSummaryFile
}

# 빈 보관함에서도 이 명령의 응답을 새 요약으로 만들지 않는다.
if (-not (Test-TtsSessionMuted)) {
    try { [System.IO.File]::WriteAllText($SummaryFile, "`r`n", (New-Object System.Text.UTF8Encoding $false)) } catch {}
}

$Newest = Get-ChildItem -Path $WavDir -Filter "tts-*.wav" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Newest) {
    Write-Output "다시 재생할 요약 음성이 없습니다."
    exit 0
}

# 파일명 tts-YYYYMMDD-HHMMSS(-ffff).wav 에서 생성 시각을 읽는다.
$When = ""
if ($Newest.Name -match '^tts-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})') {
    $When = "$($Matches[1])-$($Matches[2])-$($Matches[3]) $($Matches[4]):$($Matches[5]):$($Matches[6])"
}

if ($env:TTS_REPLAY_DRYRUN -eq "1") {
    Write-Output "file=$($Newest.FullName)"
} else {
    # 재생 대기열의 차례를 기다린 뒤 튼다(다른 세션·CLI의 음성과 겹치지 않게).
    $QueuedPlayer = Join-Path $PSScriptRoot "play-tts-queued.ps1"
    $PlayCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$QueuedPlayer`" -Path `"$($Newest.FullName)`""
    if (-not (Test-Path -LiteralPath $QueuedPlayer)) {
        # 대기열 재생기가 설치되지 않았으면 차례 없이 바로 튼다(재생이 안 되는 것보다 낫다).
        $PlayCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"[System.Media.SoundPlayer]::new('$($Newest.FullName.Replace("'", "''"))').PlaySync()`""
    }
    $StartupInfo = ([wmiclass]"Win32_ProcessStartup").CreateInstance()
    $StartupInfo.ShowWindow = 0
    $null = ([wmiclass]"Win32_Process").Create($PlayCmd, $null, $StartupInfo)
}

if ($When) {
    Write-Output "직전 요약 음성($When)을 다시 재생합니다."
} else {
    Write-Output "직전 요약 음성을 다시 재생합니다."
}
exit 0
