#
# tts-config-set.ps1 (Windows)
#
# TTS 설정 파일(<에이전트 홈>\TTS-Summary\tts-config.txt)을 터미널에서 바꾸는 설정기.
# 슬래시 명령(/tts)이 이 스크립트를 부른다. 훅이 매 턴 설정 파일을 새로 읽으므로
# 여기서 바꾼 값은 같은 턴의 재생부터 바로 적용되고 세션 재시작이 필요 없다.
#
# 사용법:
#   tts-config-set.ps1                  현재 설정 표시
#   tts-config-set.ps1 on | off         음성 요약 켬/끔
#   tts-config-set.ps1 speed 8          말하기 속도 1~10(소수점 허용)
#   tts-config-set.ps1 verbosity 2      요약 상세 정도 1~3
#   tts-config-set.ps1 interim on|off   질문 선택지 안내·중간 phase 보고 여부
#
# 주석과 나머지 줄은 그대로 두고 해당 "키=값" 줄만 바꾼다. 키가 없으면 끝에 덧붙인다.
# 원본 파일의 BOM 유무와 줄 끝(CRLF/LF)은 그대로 유지한다(파서는 둘 다 읽는다).
# 슬래시 명령은 인자 전체를 따옴표로 감싼 한 문자열로 넘기므로 아래에서 공백 기준으로 다시 나눈다.
#
# 이식 방법: $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다(.claude / .codex / .gemini).
#

param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args_)

$ErrorActionPreference = "Stop"

$AgentDirName = ".claude"   # <-- 이식 시 이 한 줄만 변경

$AgentDir = "$env:USERPROFILE\$AgentDirName"
$ConfigFile = Join-Path (Join-Path $AgentDir "TTS-Summary") "tts-config.txt"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

. (Join-Path $PSScriptRoot "tts-config.ps1")

# "speed 8" 한 덩어리로 와도 두 인자가 되도록 공백 기준으로 다시 나눈다.
$tokens = @()
foreach ($a in $Args_) { foreach ($t in ("$a" -split '\s+')) { if ($t) { $tokens += $t } } }

$Usage = "사용법: /tts [on|off] | /tts speed <1~10> | /tts verbosity <1~3> | /tts interim <on|off>. 인자 없이 실행하면 현재 설정을 보여준다."

function Fail {
    param([string]$Message)
    Write-Output $Message
    exit 1
}

# 설정 파일의 "키=값" 줄 하나를 바꾼다. 주석·빈 줄·다른 키는 그대로 둔다.
function Set-TtsKey {
    param([string]$Key, [string]$Value)
    if (-not (Test-Path -LiteralPath $ConfigFile)) { Fail "설정 파일이 없습니다: $ConfigFile" }
    # 원본의 BOM 유무와 줄 끝을 그대로 되돌려 쓰기 위해 바이트로 읽는다.
    $bytes = [System.IO.File]::ReadAllBytes($ConfigFile)
    $hadBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $body = [System.Text.Encoding]::UTF8.GetString($bytes)
    if ($hadBom) { $body = $body.Substring(1) }
    $newline = if ($body -match "`r`n") { "`r`n" } else { "`n" }
    $lines = @($body -split "`r?`n")
    if ($lines.Count -gt 0 -and $lines[-1] -eq "") { $lines = $lines[0..($lines.Count - 2)] }
    $done = $false
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        $trimmed = "$line".Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or ($trimmed.IndexOf("=") -lt 1)) {
            $out.Add($line); continue
        }
        $k = $trimmed.Substring(0, $trimmed.IndexOf("=")).Trim().ToLowerInvariant()
        if ($k -eq $Key) {
            if (-not $done) { $out.Add("$Key=$Value"); $done = $true }
            continue
        }
        $out.Add($line)
    }
    if (-not $done) { $out.Add("$Key=$Value") }
    $text = ($out -join $newline) + $newline
    [System.IO.File]::WriteAllText($ConfigFile, $text, (New-Object System.Text.UTF8Encoding($hadBom)))
}

function Show-TtsConfig {
    $config = Get-TtsConfig $AgentDir
    $state = if (Test-TtsEnabled $config) { "켬" } else { "끔" }
    $interim = if (Test-TtsInterimEnabled $config) { "켬" } else { "끔" }
    $rate = ConvertTo-SapiRate $config.speed
    $provider = Get-TtsProvider $config
    $voice = switch ($provider) {
        "gemini-api"     { $config.voice_gemini }
        "elevenlabs-api" { $config.voice_elevenlabs }
        default          { $config.voice_sapi }
    }
    $line = "TTS 음성 요약 $state, 속도 $($config.speed)(SAPI Rate $rate), 상세 $($config.verbosity)단계, 선택지·중간 보고 $interim, 프로바이더 $provider"
    if ("$voice".Trim()) { $line += ", 음성 $($voice.Trim())" }
    Write-Output $line
}

if ($tokens.Count -eq 0) { Show-TtsConfig; exit 0 }

switch ($tokens[0].ToLowerInvariant()) {
    { $_ -in @("on", "off") } {
        if ($tokens.Count -ne 1) { Fail $Usage }
        Set-TtsKey "enabled" $tokens[0].ToLowerInvariant()
    }
    "speed" {
        if ($tokens.Count -ne 2) { Fail $Usage }
        $value = 0.0
        if (-not [double]::TryParse($tokens[1], [ref]$value)) { Fail "속도는 1~10 사이 숫자여야 합니다(소수점 허용): $($tokens[1])" }
        if ($value -lt 1 -or $value -gt 10) { Fail "속도는 1~10 사이여야 합니다: $($tokens[1])" }
        Set-TtsKey "speed" $tokens[1]
    }
    "verbosity" {
        if ($tokens.Count -ne 2) { Fail $Usage }
        if ($tokens[1] -notin @("1", "2", "3")) { Fail "상세 정도는 1, 2, 3 중 하나여야 합니다: $($tokens[1])" }
        Set-TtsKey "verbosity" $tokens[1]
    }
    "interim" {
        if ($tokens.Count -ne 2) { Fail $Usage }
        $value = $tokens[1].ToLowerInvariant()
        if ($value -notin @("on", "off")) { Fail "interim 값은 on 또는 off여야 합니다: $($tokens[1])" }
        Set-TtsKey "interim" $value
    }
    { $_ -in @("-h", "--help", "help") } { Write-Output $Usage; exit 0 }
    default { Fail $Usage }
}

Show-TtsConfig
