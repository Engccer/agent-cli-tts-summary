#
# TTS 설정 파일(TTS-Summary 폴더의 tts-config.txt) 파서.
# stop-tts.ps1, tts-config-context.ps1, play-tts-*.ps1이 함께 dot-source 한다.
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
    if ($provider -notin @("windows-sapi", "gemini-api", "elevenlabs-api")) { return "windows-sapi" }
    return $provider
}
