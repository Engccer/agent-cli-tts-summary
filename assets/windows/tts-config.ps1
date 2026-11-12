#
# TTS 설정 파일(TTS-Summary 폴더의 tts-config.txt) 파서.
# stop-tts.ps1, tts-config-context.ps1, play-tts-*.ps1, ask-question-tts.ps1, tts-config-set.ps1, tts-replay.ps1이 함께 dot-source 한다.
#
# 이 설정 파일이 유일한 정본이며 음성·속도를 담는 별도 파일은 없다.
# stop-tts.ps1, provider 재생 스크립트 3종, 설정 통지 훅, 질문 선택지 안내, 중간 보고가 모두 이 파서로 설정을 읽는다.
#

function Get-TtsConfig {
    param([string]$AgentDir)

    $config = @{
        enabled          = "on"
        speed            = "7.5"
        verbosity        = "2"
        interim          = "off"
        provider         = "windows-sapi"
        voice_sapi       = ""
        voice_gemini     = ""
        voice_elevenlabs = ""
        voice_azure      = ""
        language_code    = "ko-KR"
    }

    $configFile = Join-Path (Join-Path $AgentDir "TTS-Summary") "tts-config.txt"
    if (-not (Test-Path $configFile)) { return $config }

    try {
        foreach ($line in (Get-Content -LiteralPath $configFile -Encoding UTF8)) {
            $trimmed = $line.Trim()
            if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
            $sep = $trimmed.IndexOf("=")
            if ($sep -lt 1) { continue }
            $key = $trimmed.Substring(0, $sep).Trim().ToLowerInvariant()
            $value = $trimmed.Substring($sep + 1).Trim()
            if ($config.ContainsKey($key)) { $config[$key] = $value }
        }
    } catch {}

    return $config
}

function Test-TtsEnabled {
    param($Config)
    return ($Config.enabled -notmatch '^(off|0|false|no)$')
}

# 이 세션에 한해 요약 루프를 끄는 환경 변수. 병렬 세션 런처(parallel-sessions 스킬)가 작업
# 세션을 띄울 때 TTS_SUMMARY=off를 심는다. 그 세션의 프로세스 트리에만 걸린다(훅은 CLI의 자식).
function Test-TtsSessionMuted {
    return ([string]$env:TTS_SUMMARY -match '^\s*(off|0|false|no)\s*$')
}

# 훅 payload(stdin JSON)에서 이 대화 세션의 식별자를 읽는다. Claude·Codex는 session_id,
# Antigravity는 conversationId(없으면 환경 변수 ANTIGRAVITY_CONVERSATION_ID)다.
# 파일 이름으로 쓰므로 영숫자·밑줄·하이픈만 받아들이고, 얻지 못하면 빈 문자열을 돌려준다.
function Get-TtsSessionId {
    param([string]$HookInput, [string]$AgentDirName)
    $sid = ""
    if ("$HookInput".Trim()) {
        try {
            $payload = $HookInput | ConvertFrom-Json
            if ($payload.session_id) { $sid = "$($payload.session_id)" }
            elseif ($payload.conversationId) { $sid = "$($payload.conversationId)" }
        } catch {}
    }
    if (-not $sid -and $AgentDirName -eq ".gemini") { $sid = "$env:ANTIGRAVITY_CONVERSATION_ID" }
    if ($sid -match '\A[A-Za-z0-9_-]{1,128}\z') { return $sid }
    return ""
}

# 세션 전용 요약 파일. 같은 CLI를 여러 터미널에서 동시에 돌려도 세션마다 파일이 달라
# 서로 덮어쓰거나 남의 요약을 읽어 가지 않는다. 세션 식별자가 없으면 빈 문자열(공용 tts-summary.txt 사용).
function Get-TtsSessionSummaryFile {
    param([string]$AgentDir, [string]$SessionId)
    if (-not $SessionId) { return "" }
    return "$AgentDir\TTS-Summary\pending\$SessionId.txt"
}

# 재생 대기열. 소리를 내는 모든 경로(요약, 중간 보고, 질문 안내, 다시 재생)가 머신 전역 뮤텍스 하나를
# 차례로 쥐어, 여러 세션·여러 CLI의 음성이 겹치지 않고 먼저 온 것부터 이어서 들린다.
# 제한 시간 안에 차례가 오지 않으면 기다림을 그만두고 그대로 재생한다(요약이 들리지 않는 것보다 겹치는 편이 낫다).
function Enter-TtsPlaybackQueue {
    param([int]$TimeoutSeconds = 240)
    $name = "$env:TTS_PLAYBACK_QUEUE_NAME"
    if (-not $name) { $name = "Global\AgentCliTtsSummaryPlayback" }
    try {
        $mutex = New-Object System.Threading.Mutex($false, $name)
        $owned = $false
        try { $owned = $mutex.WaitOne([TimeSpan]::FromSeconds($TimeoutSeconds)) }
        catch {
            # 뮤텍스를 쥔 프로세스가 풀지 못하고 죽었으면 소유권이 넘어온 것이다.
            $owned = ($_.Exception -is [System.Threading.AbandonedMutexException]) -or
                     ($_.Exception.InnerException -is [System.Threading.AbandonedMutexException])
        }
        return @{ Mutex = $mutex; Owned = $owned }
    } catch { return $null }
}

function Exit-TtsPlaybackQueue {
    param($Queue)
    if (-not $Queue) { return }
    try { if ($Queue.Owned) { $Queue.Mutex.ReleaseMutex() } } catch {}
    try { $Queue.Mutex.Dispose() } catch {}
}

# 응답 완료 전 발화(질문 선택지 안내, 중간 phase 보고) 여부. enabled가 꺼져 있으면 무관하다.
function Test-TtsInterimEnabled {
    param($Config)
    return ($Config.interim -notmatch '^(off|0|false|no)$')
}

# 속도 1~10 -> SAPI Rate -10~10. speed 5가 보통 속도, 10이 최고 속도.
# SAPI Rate는 규격 자체가 -10~10이라 speed 10에서 이미 엔진 최대치다.
# 아래 ConvertTo-TtsTempo(API provider용)와 달리 이 경로는 더 가팔라질 여지가 없다.
function ConvertTo-SapiRate {
    param([string]$Speed)
    $value = 0.0
    if (-not [double]::TryParse($Speed, [ref]$value)) { return $null }
    if ($value -lt 1) { $value = 1 }
    if ($value -gt 10) { $value = 10 }
    return [int][Math]::Round(2 * $value - 10)
}

# 속도 1~10 -> API provider 재생 배율 0.5~4.0 (macOS tts-config.sh와 같은 곡선).
# 고정점은 speed 5 = 배율 1.0.
#   1~5 구간: 선형(1이 0.6)
#   5~10 구간: 2.5단계마다 두 배가 되는 기하 곡선(10이 4.0)
# 기하로 잡는 이유: 체감 속도는 비율이라 2배와 4배가 같은 크기의 한 걸음이다.
function ConvertTo-TtsTempo {
    param([string]$Speed)
    $value = 0.0
    if (-not [double]::TryParse($Speed, [ref]$value)) { return 1.0 }
    if ($value -lt 1) { $value = 1 }
    if ($value -gt 10) { $value = 10 }
    if ($value -ge 5) { $tempo = [Math]::Pow(2, ($value - 5) / 2.5) }
    else { $tempo = 1.0 + ($value - 5) * 0.1 }
    if ($tempo -lt 0.5) { return 0.5 }
    if ($tempo -gt 4.0) { return 4.0 }
    # 소수점 둘째 자리에서 끊는다. macOS tts_tempo가 "%.2f"로 내보내므로
    # 여기서 반올림해야 두 플랫폼의 배율과 atempo 체인이 정확히 같은 값이 된다.
    return [Math]::Round($tempo, 2)
}

# ffmpeg -filter:a 에 넘길 atempo 필터. 2.0을 넘는 배율은 체인으로 나눈다
# (예: 4.0 -> "atempo=2.0,atempo=2.0000").
# 최신 ffmpeg(8.1)의 atempo는 0.5~100을 받아 나눌 필요가 없지만, 옛 빌드는 상한이 2.0이라
# 단일 필터를 거부하고 그때 속도 설정이 조용히 무시된다. 버전을 가리지 않게 체인으로 둔다.
function Get-AtempoFilter {
    param([double]$Tempo)
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    $chain = ""
    while ($Tempo -gt 2.0000001) {
        $chain += "atempo=2.0,"
        $Tempo = $Tempo / 2.0
    }
    return $chain + "atempo=" + $Tempo.ToString("0.0000", $culture)
}

# provider 값 정규화. 인식되지 않으면 OS 내장 SAPI로 떨어뜨린다.
function Get-TtsProvider {
    param($Config)
    $provider = "$($Config.provider)".Trim().ToLowerInvariant()
    if ($provider -notin @("windows-sapi", "gemini-api", "elevenlabs-api", "azure-api")) { return "windows-sapi" }
    return $provider
}
