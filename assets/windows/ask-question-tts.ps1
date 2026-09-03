#
# ask-question-tts.ps1 (Windows)
#
# PreToolUse hook. 선택 질문 도구 호출 직전 stdin의 tool_input(질문 JSON)을 읽어
# "질문 본문 + 선택지 라벨"을 한국어로 조립한 뒤 같은 폴더의 play-tts-briefing.ps1로
# 숨김 분리 재생한다. 도구 호출을 절대 차단하지 않으며 어떤 경우에도 exit 0.
#
# matcher는 에이전트별 실제 도구명을 쓴다(다른 이름을 등록하면 절대 발동하지 않는다):
# - Claude Code: AskUserQuestion
# - Codex CLI: request_user_input
# 두 도구의 tool_input은 동형(questions[].question/header + options[].label)이라 이 스크립트
# 하나가 양쪽 payload를 그대로 처리한다.
#
# 정책: 질문 + 선택지 라벨까지 읽고, 선택지 설명은 생략한다(스크린리더가 TUI 탐색 중
# 설명을 읽어주므로 중복을 피한다).
# 설정 파일(TTS-Summary\tts-config.txt)의 enabled와 interim이 모두 on일 때만 발화한다.
#
# 이식 방법: $AgentDirName 한 줄만 대상 에이전트 폴더명으로 바꾼다(.claude / .codex / .gemini).
# 디버그: ASK_TTS_DRYRUN=1 이면 발화 대신 조립된 문장을 stdout에 출력한다.
#

$ErrorActionPreference = "SilentlyContinue"

$AgentDirName = ".claude"   # <-- 이식 시 이 한 줄만 변경

$AgentDir = "$env:USERPROFILE\$AgentDirName"
try { [Console]::InputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

. (Join-Path $PSScriptRoot "tts-config.ps1")
$config = Get-TtsConfig $AgentDir
if (-not (Test-TtsEnabled $config)) { exit 0 }
if (-not (Test-TtsInterimEnabled $config)) { exit 0 }

$raw = ""
try { $raw = [Console]::In.ReadToEnd() } catch {}
if (-not "$raw".Trim()) { exit 0 }

$payload = $null
try { $payload = $raw | ConvertFrom-Json } catch { exit 0 }
$questions = $payload.tool_input.questions
if (-not $questions) { exit 0 }

$parts = @()
$multi = @($questions).Count -gt 1
$index = 0
foreach ($q in @($questions)) {
    $index++
    $question = "$($q.question)".Trim()
    if (-not $question) { $question = "$($q.header)".Trim() }
    if (-not $question) { continue }
    $labels = @()
    foreach ($o in @($q.options)) {
        $label = "$($o.label)".Trim()
        if ($label) { $labels += $label }
    }
    $sentence = if ($multi) { "${index}번 질문: $question" } else { "질문: $question" }
    if ($labels.Count -gt 0) {
        $sentence += " 선택지는 " + ($labels -join ", ") + ", 그리고 기타 직접 입력입니다."
    }
    $parts += $sentence
}
if ($parts.Count -eq 0) { exit 0 }
$speak = $parts -join " "

if ($env:ASK_TTS_DRYRUN -eq "1") {
    Write-Output $speak
    exit 0
}

# 분리 프로세스는 부모 환경 변수를 물려받지 않으므로 음성·속도를 인자로 넘긴다.
$rate = ConvertTo-SapiRate $config.speed
$voice = "$($config.voice_sapi)".Trim()
$briefing = Join-Path $PSScriptRoot "play-tts-briefing.ps1"
if (Test-Path -LiteralPath $briefing) {
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("tts-ask-" + [System.IO.Path]::GetRandomFileName() + ".txt")
    [System.IO.File]::WriteAllText($tmp, $speak, (New-Object System.Text.UTF8Encoding $false))
    $cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$briefing`" -TextFile `"$tmp`" -Speak -Rate `"$rate`" -Voice `"$voice`""
    $startup = ([wmiclass]"Win32_ProcessStartup").CreateInstance()
    $startup.ShowWindow = 0
    $result = ([wmiclass]"Win32_Process").Create($cmd, $null, $startup)
    # 분리 프로세스가 뜨지 못하면 그 프로세스가 지울 임시 파일을 여기서 지운다.
    if (-not $result -or $result.ReturnValue -ne 0) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
}

exit 0
