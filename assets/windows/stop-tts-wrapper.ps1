#
# Stop hook wrapper (Gemini/Antigravity, Windows) - stop-tts.ps1을 합성 전용으로 실행하고,
# 생성된 WAV를 숨김 분리 프로세스로 재생한 뒤 순수 JSON만 stdout으로 낸다.
#
# 이유 1) Antigravity는 훅 프로세스 정리 시 자식 재생을 끊을 수 있어 분리 재생이 필요하다.
# 이유 2) Gemini/Antigravity 훅 stdout은 JSON schema를 기대하므로 진단은 로그로 보낸다.
# provider 선택·폴백·보관은 전부 같은 폴더의 stop-tts.ps1이 담당한다(tts-provider.txt).
# 이식 방법: $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다.
#

$ErrorActionPreference = "SilentlyContinue"

$AgentDirName = ".gemini"   # <-- 이식 시 변경

$AgentDir   = "$env:USERPROFILE\$AgentDirName"
$HookDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$StopScript = Join-Path $HookDir "stop-tts.ps1"
$WavDir     = "$AgentDir\TTS-Summary\wav"
$LogFile    = "$AgentDir\log\stop-wrapper.log"

New-Item -ItemType Directory -Path (Split-Path -Parent $LogFile) -Force | Out-Null

$Before = Get-Date

# 합성 전용 실행: 재생은 이 wrapper가 분리 프로세스로 담당한다.
# 호출자가 이미 TTS_NO_PLAY를 세팅했으면(검증 등) 분리 재생도 생략한다.
$HadNoPlay = [bool]$env:TTS_NO_PLAY
$env:TTS_NO_PLAY = "1"

$HookInput = ""
try { $HookInput = [Console]::In.ReadToEnd() } catch {}
$HookInput | & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript *>> $LogFile

if (-not $HadNoPlay) {
    Remove-Item Env:TTS_NO_PLAY -ErrorAction SilentlyContinue

    # 이번 실행에서 생성된 WAV만 재생 대상으로 삼는다.
    $Newest = Get-ChildItem -Path $WavDir -Filter "tts-*.wav" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $Before } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($Newest) {
        $EscapedPath = $Newest.FullName.Replace("'", "''")
        $PlayCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"[System.Media.SoundPlayer]::new('$EscapedPath').PlaySync()`""
        $StartupInfo = ([wmiclass]"Win32_ProcessStartup").CreateInstance()
        $StartupInfo.ShowWindow = 0
        $null = ([wmiclass]"Win32_Process").Create($PlayCmd, $null, $StartupInfo)
    }
}

# Gemini/Antigravity CLI가 요구하는 순수 JSON 응답만 stdout으로 출력한다.
@{ decision = "proceed" } | ConvertTo-Json -Compress
exit 0
