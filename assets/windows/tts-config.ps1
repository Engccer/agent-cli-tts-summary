#
# TTS 설정 파일(TTS-Summary 폴더의 tts-config.txt) 파서.
# stop-tts.ps1, tts-config-context.ps1, play-tts-*.ps1이 함께 dot-source 한다.
#
# 이 설정 파일이 유일한 정본이다. 예전에 쓰던 개별 파일(tts-provider.txt,
# tts-speech-rate.txt, tts-voice-*.txt, tts-language-code.txt)은 폐지했고,
# stop-tts.ps1과 provider 재생 스크립트 3종이 모두 이 파서를 통해 설정을 읽는다.
#

function Get-TtsConfig {
    param([string]$AgentDir)

    $config = @{
        enabled          = "on"
        speed            = "7.5"
        verbosity        = "2"
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

# 속도 1~10 -> SAPI Rate -10~10. speed 5가 보통 속도, 10이 최고 속도.
function ConvertTo-SapiRate {
    param([string]$Speed)
    $value = 0.0
    if (-not [double]::TryParse($Speed, [ref]$value)) { return $null }
    if ($value -lt 1) { $value = 1 }
    if ($value -gt 10) { $value = 10 }
    return [int][Math]::Round(2 * $value - 10)
}

# provider 값 정규화. 인식되지 않으면 OS 내장 SAPI로 떨어뜨린다.
function Get-TtsProvider {
    param($Config)
    $provider = "$($Config.provider)".Trim().ToLowerInvariant()
    if ($provider -notin @("windows-sapi", "gemini-api", "elevenlabs-api")) { return "windows-sapi" }
    return $provider
}
