#
# play-tts-queued.ps1 (Windows) - 이미 만들어진 WAV 한 개를 재생 대기열의 차례에 맞춰 재생한다.
# stop-tts-wrapper.ps1(Antigravity 요약)과 tts-replay.ps1(다시 재생)이 숨김 분리 프로세스로 부른다.
# 대기열은 같은 폴더 tts-config.ps1의 Enter-TtsPlaybackQueue다. 다른 세션·다른 CLI의 음성이
# 재생 중이면 끝날 때까지 기다렸다가 이어서 튼다.
#
# 사용법: powershell.exe -NoProfile -ExecutionPolicy Bypass -File play-tts-queued.ps1 -Path <wav>
# 검증: TTS_NO_PLAY가 있으면 대기열만 지나고 재생하지 않는다.
#

param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = "SilentlyContinue"

. (Join-Path $PSScriptRoot "tts-config.ps1")

if (-not (Test-Path -LiteralPath $Path)) { exit 0 }

# 훅에 묶이지 않은 분리 프로세스라 차례를 넉넉히 기다린다.
$Queue = Enter-TtsPlaybackQueue -TimeoutSeconds 600
try {
    if (-not $env:TTS_NO_PLAY) {
        $player = New-Object System.Media.SoundPlayer $Path
        $player.PlaySync()
        $player.Dispose()
    }
} catch {
} finally {
    Exit-TtsPlaybackQueue $Queue
}

exit 0
