#
# Stop hook wrapper (Antigravity, Windows) - stop-tts.ps1을 합성 전용으로 실행하고,
# 생성된 WAV를 숨김 분리 프로세스로 재생한 뒤 순수 JSON만 stdout으로 낸다.
#
# 이유 1) Antigravity는 훅 프로세스 정리 시 자식 재생을 끊을 수 있어 분리 재생이 필요하다.
# 이유 2) Antigravity 훅 stdout은 JSON schema를 기대하므로 진단은 로그로 보낸다.
# provider 선택·폴백·보관은 전부 같은 폴더의 stop-tts.ps1이 담당한다(설정 파일의 provider).
# 설정이 enabled=off면 stop-tts.ps1이 WAV를 만들지 않으므로 이 wrapper도 아무것도 재생하지 않는다.
# 이식 방법: $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다.
#

$ErrorActionPreference = "SilentlyContinue"
try { [Console]::InputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$AgentDirName = ".gemini"   # <-- 이식 시 변경

$AgentDir   = "$env:USERPROFILE\$AgentDirName"
$HookDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$StopScript = Join-Path $HookDir "stop-tts.ps1"
$LogFile    = "$AgentDir\log\stop-wrapper.log"

New-Item -ItemType Directory -Path (Split-Path -Parent $LogFile) -Force | Out-Null

# 합성 전용 실행: 재생은 이 wrapper가 분리 프로세스로 담당한다.
# 호출자가 이미 TTS_NO_PLAY를 세팅했으면(검증 등) 분리 재생도 생략한다.
$HadNoPlay = [bool]$env:TTS_NO_PLAY
$env:TTS_NO_PLAY = "1"

$HookInput = ""
try { $HookInput = [Console]::In.ReadToEnd() } catch {}
# stop-tts.ps1이 이번 실행에서 만든 음성 파일 경로를 이 파일로 넘겨준다.
$AudioPathFile = Join-Path ([System.IO.Path]::GetTempPath()) ("tts-audio-" + [System.IO.Path]::GetRandomFileName() + ".txt")
$env:TTS_AUDIO_PATH_FILE = $AudioPathFile
# 자식 출력은 변수로 받아 둔다. 로그 파일로 바로 리디렉션하면 다른 세션의 wrapper가 같은 로그를
# 쥐고 있을 때 stop-tts.ps1이 실행조차 되지 않아 그 요약이 사라진다.
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
$StopOutput = @($HookInput | & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript 2>&1)
$StopExit = $LASTEXITCODE
try { Add-Content -LiteralPath $LogFile -Value @($StopOutput | ForEach-Object { "$_" }) -Encoding UTF8 } catch {}
Remove-Item Env:TTS_AUDIO_PATH_FILE -ErrorAction SilentlyContinue

$AudioPath = ""
if (Test-Path -LiteralPath $AudioPathFile) {
    $AudioPath = "$(Get-Content -LiteralPath $AudioPathFile -Raw -Encoding UTF8)".Trim()
    Remove-Item -LiteralPath $AudioPathFile -Force -ErrorAction SilentlyContinue
}

if (-not $HadNoPlay) {
    Remove-Item Env:TTS_NO_PLAY -ErrorAction SilentlyContinue

    # 재생 대상은 stop-tts.ps1이 알려 준 이번 실행의 파일뿐이다. 보관 폴더에서 가장 새 WAV를 고르지 않는다
    # (동시에 끝난 다른 세션의 음성을 한 번 더 틀게 된다).
    if ($StopExit -eq 0 -and $AudioPath -and (Test-Path -LiteralPath $AudioPath)) {
        # 분리 재생은 play-tts-queued.ps1이 재생 대기열의 차례를 기다린 뒤 맡는다(다른 세션·CLI의 음성과 겹치지 않게).
        $QueuedPlayer = Join-Path $HookDir "play-tts-queued.ps1"
        $PlayCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$QueuedPlayer`" -Path `"$AudioPath`""
        if (-not (Test-Path -LiteralPath $QueuedPlayer)) {
            # 대기열 재생기가 설치되지 않았으면 차례 없이 바로 튼다(요약이 들리지 않는 것보다 낫다).
            $PlayCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"[System.Media.SoundPlayer]::new('$($AudioPath.Replace("'", "''"))').PlaySync()`""
        }
        $StartupInfo = ([wmiclass]"Win32_ProcessStartup").CreateInstance()
        $StartupInfo.ShowWindow = 0
        $null = ([wmiclass]"Win32_Process").Create($PlayCmd, $null, $StartupInfo)
    }
}

# Antigravity CLI가 요구하는 순수 JSON 응답만 stdout으로 출력한다.
if ($StopExit -eq 2) {
    # 요약을 쓸 자리는 stop-tts.ps1과 같은 규칙으로 정한다: 세션 전용 파일이 먼저, 세션 식별자가 없으면 공용 파일.
    . (Join-Path $HookDir "tts-config.ps1")
    $WriteTarget = Get-TtsSessionSummaryFile $AgentDir (Get-TtsSessionId $HookInput $AgentDirName)
    if (-not $WriteTarget) { $WriteTarget = "$AgentDir\tts-summary.txt" }
    $Reason = "TTS 요약 누락: 글로벌 지침(CLAUDE.md/AGENTS.md/GEMINI.md)의 TTS 요약 규칙에 따라(지정된 요약 언어 포함) 이번 응답의 요약을 $WriteTarget 에 파일 편집 도구로 작성한 뒤 응답을 마치세요."
    @{ decision = "continue"; reason = $Reason } | ConvertTo-Json -Compress
} else {
    @{ decision = "proceed" } | ConvertTo-Json -Compress
}
exit 0
