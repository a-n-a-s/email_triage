<#
.SYNOPSIS
    OpenEnv Submission Validator for Windows (PowerShell)
.DESCRIPTION
    Checks that your HF Space is live, submission requirements pass, and Docker builds.
.PARAMETER PingUrl
    Your HuggingFace Space URL (e.g. https://akanaspro-email-triage.hf.space)
.PARAMETER RepoDir
    Path to your repo (default: current directory)
.EXAMPLE
    .\validate-submission.ps1 -PingUrl "https://akanaspro-email-triage.hf.space"
    .\validate-submission.ps1 -PingUrl "https://akanaspro-email-triage.hf.space" -RepoDir "D:\email_triage\email_triage"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$PingUrl,

    [string]$RepoDir = "."
)

$script:Pass = 0
$script:Fail = 0
$script:Warn = 0

function PassCheck { param($Msg); Write-Host "  ✅ PASS  $Msg" -ForegroundColor Green; $script:Pass++ }
function FailCheck { param($Msg); Write-Host "  ❌ FAIL  $Msg" -ForegroundColor Red; $script:Fail++ }
function WarnCheck { param($Msg); Write-Host "  ⚠️  WARN  $Msg" -ForegroundColor Yellow; $script:Warn++ }

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗"
Write-Host "║  📋  OPENENV SUBMISSION VALIDATOR                       ║"
Write-Host "╠══════════════════════════════════════════════════════════╣"
Write-Host "║  🌐  Space : $PingUrl"
Write-Host "║  📁  Repo  : $RepoDir"
Write-Host "╚══════════════════════════════════════════════════════════╝"
Write-Host ""

# ──────────────────────────────────────────────────────────────
# 1. HF Space Deploys
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[1/11] HF Space Deploys"
try {
    # HF Spaces with FastAPI may not define root route, so test /health
    $resp = Invoke-WebRequest -Uri "$PingUrl/health" -Method Get -TimeoutSec 30 -UseBasicParsing
    if ($resp.StatusCode -eq 200) { PassCheck "Space responds (HTTP 200 on /health)" }
    else { FailCheck "Space returned HTTP $($resp.StatusCode) (expected 200)" }
} catch {
    FailCheck "Space unreachable: $_"
}

# ──────────────────────────────────────────────────────────────
# 2. Health Endpoint
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[2/11] Health Endpoint"
try {
    $health = Invoke-RestMethod -Uri "$PingUrl/health" -Method Get -TimeoutSec 30 -UseBasicParsing
    if ($health.status -eq "healthy") { PassCheck "/health returns healthy status" }
    else { FailCheck "/health returned status: $($health.status)" }
} catch {
    FailCheck "/health unreachable: $_"
}

# ──────────────────────────────────────────────────────────────
# 3. Reset Endpoint
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[3/11] Reset Endpoint (/openenv/reset)"
try {
    $reset = Invoke-RestMethod -Uri "$PingUrl/openenv/reset" -Method Post -ContentType "application/json" -Body "{}" -TimeoutSec 30 -UseBasicParsing
    if ($reset.observation -and $reset.observation.task_id -and $reset.observation.emails) {
        PassCheck "/openenv/reset returns valid observation"
    } else { FailCheck "/openenv/reset missing required fields" }
} catch {
    FailCheck "/openenv/reset failed: $_"
}

# ──────────────────────────────────────────────────────────────
# 4. Step Endpoint (Task 1: Spam)
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[4/11] Step Endpoint - Task 1 (Spam)"
try {
    $step1 = Invoke-RestMethod -Uri "$PingUrl/openenv/step" -Method Post -ContentType "application/json" -Body '{"action":{"task_id":1,"label":"spam"}}' -TimeoutSec 30 -UseBasicParsing
    $reward1 = $step1.reward
    $task2 = $step1.observation.task_id
    if ($reward1 -ne $null -and $task2 -eq 2) {
        PassCheck "Task 1: reward=$reward1, advanced to Task 2"
    } else { FailCheck "Task 1: invalid response (reward=$reward1, next=$task2)" }
} catch {
    FailCheck "Task 1 step failed: $_"
}

# ──────────────────────────────────────────────────────────────
# 5. Step Endpoint (Task 2: Ranking)
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[5/11] Step Endpoint - Task 2 (Ranking)"
try {
    $step2 = Invoke-RestMethod -Uri "$PingUrl/openenv/step" -Method Post -ContentType "application/json" -Body '{"action":{"task_id":2,"ranking":[0,1,2]}}' -TimeoutSec 30 -UseBasicParsing
    $reward2 = $step2.reward
    $task3 = $step2.observation.task_id
    if ($reward2 -ne $null -and $task3 -eq 3) {
        PassCheck "Task 2: reward=$reward2, advanced to Task 3"
    } else { FailCheck "Task 2: invalid response (reward=$reward2, next=$task3)" }
} catch {
    FailCheck "Task 2 step failed: $_"
}

# ──────────────────────────────────────────────────────────────
# 6. Step Endpoint (Task 3: Reply)
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[6/11] Step Endpoint - Task 3 (Reply)"
try {
    $step3 = Invoke-RestMethod -Uri "$PingUrl/openenv/step" -Method Post -ContentType "application/json" -Body '{"action":{"task_id":3,"action_type":"reply","reply_text":"Thank you for your email. I confirm the deadline and deliverables."}}' -TimeoutSec 30 -UseBasicParsing
    $reward3 = $step3.reward
    $done = $step3.done
    if ($reward3 -ne $null -and $done -eq $true) {
        PassCheck "Task 3: reward=$reward3, episode complete"
    } else { FailCheck "Task 3: invalid response (reward=$reward3, done=$done)" }
} catch {
    FailCheck "Task 3 step failed: $_"
}

# ──────────────────────────────────────────────────────────────
# 7. Scores in 0.0-1.0 Range
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[7/11] Scores in Valid Range (0.0-1.0)"
$allValid = $true
foreach ($r in @($reward1, $reward2, $reward3)) {
    if ($r -lt 0.0 -or $r -gt 1.0) { $allValid = $false }
}
if ($allValid) {
    PassCheck "All rewards in [0.0, 1.0]: $reward1, $reward2, $reward3"
} else {
    FailCheck "Some rewards outside [0.0, 1.0] range"
}

# ──────────────────────────────────────────────────────────────
# 8. openenv.yaml Present
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[8/11] openenv.yaml Present"
$openenvPath = Join-Path $RepoDir "openenv.yaml"
if (Test-Path $openenvPath) {
    $content = Get-Content $openenvPath -Raw
    if ($content -match "name:" -and $content -match "sdk:\s*docker") {
        PassCheck "openenv.yaml exists with required fields (name, sdk=docker)"
    } else {
        FailCheck "openenv.yaml exists but missing required fields"
    }
} else {
    FailCheck "openenv.yaml not found in repo root"
}

# ──────────────────────────────────────────────────────────────
# 9. inference.py in Root + Required Env Vars
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[9/11] inference.py + Required Env Vars"
$inferencePath = Join-Path $RepoDir "inference.py"
if (Test-Path $inferencePath) {
    PassCheck "inference.py found in root directory"

    $content = Get-Content $inferencePath -Raw
    $missing = @()
    foreach ($var in @("API_BASE_URL", "MODEL_NAME", "HF_TOKEN")) {
        if ($content -notmatch "os\.getenv\([`"']$var[`"']") { $missing += $var }
    }
    if ($missing.Count -eq 0) {
        PassCheck "All required env vars defined: API_BASE_URL, MODEL_NAME, HF_TOKEN"
    } else {
        FailCheck "Missing env vars: $($missing -join ', ')"
    }
} else {
    FailCheck "inference.py not found in root directory"
}

# ──────────────────────────────────────────────────────────────
# 10. OpenAI Client + STDOUT Format
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[10/11] OpenAI Client + STDOUT Format"
if (Test-Path $inferencePath) {
    $content = Get-Content $inferencePath -Raw
    if ($content -match "from openai import OpenAI") {
        PassCheck "Uses OpenAI Client (from openai import OpenAI)"
    } else {
        FailCheck "Missing: from openai import OpenAI"
    }

    if ($content -match "\[START\]" -and $content -match "\[STEP\]" -and $content -match "\[END\]") {
        PassCheck "STDOUT format includes [START], [STEP], [END]"
    } else {
        FailCheck "Missing [START]/[STEP]/[END] in stdout format"
    }
}

# ──────────────────────────────────────────────────────────────
# 11. Docker Build (Optional)
# ──────────────────────────────────────────────────────────────
Write-Host -ForegroundColor White "[11/11] Docker Build (Optional)"
$dockerfile = Join-Path $RepoDir "Dockerfile"
if (Test-Path $dockerfile) {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Host "  Building Docker image (timeout: 600s)..." -ForegroundColor Gray
        $job = Start-Job -ScriptBlock { docker build -t email-triage-validate $args[0] 2>&1 } -ArgumentList $RepoDir
        $completed = Wait-Job $job -Timeout 600
        if ($completed) {
            $output = Receive-Job $job
            if ($LASTEXITCODE -eq 0) {
                PassCheck "Docker build succeeded"
                docker rmi email-triage-validate 2>$null
            } else {
                WarnCheck "Docker build failed (check logs)"
            }
        } else {
            Stop-Job $job; Remove-Job $job -Force
            WarnCheck "Docker build timed out after 600s"
        }
    } else {
        WarnCheck "Docker not installed — skipping build test"
    }
} else {
    FailCheck "Dockerfile not found"
}

# ──────────────────────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────────────────────
$Total = $script:Pass + $script:Fail + $script:Warn
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗"
Write-Host "║  📊  VALIDATION SUMMARY                                 ║"
Write-Host "╠══════════════════════════════════════════════════════════╣"
Write-Host "║  ✅  Passed : $($script:Pass)" -ForegroundColor Green
Write-Host "║  ❌  Failed : $($script:Fail)" -ForegroundColor Red
Write-Host "║  ⚠️  Warnings: $($script:Warn)" -ForegroundColor Yellow
Write-Host "║  📋  Total  : $Total"
Write-Host "╚══════════════════════════════════════════════════════════╝"
Write-Host ""

if ($script:Fail -eq 0) {
    Write-Host -ForegroundColor Green -Bold "🎉  ALL CHECKS PASSED — Ready to submit!"
    Write-Host ""
    exit 0
} else {
    Write-Host -ForegroundColor Red -Bold "❌  $($script:Fail) check(s) failed — fix before submitting"
    Write-Host ""
    exit 1
}
