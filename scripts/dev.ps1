Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $PSScriptRoot
$port = 8000

function Assert-ExitCode {
    param(
        [int]$Code,
        [string]$Step
    )
    if ($Code -ne 0) {
        throw "Step failed: $Step (exit code $Code)"
    }
}

Write-Host "[1/4] Checking port $port..."
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $listener) {
    $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    $procName = if ($null -ne $process) { $process.ProcessName } else { "unknown" }
    throw "Port $port is already in use by PID $($listener.OwningProcess) ($procName). Stop that process and retry."
}

Write-Host "[2/4] Syncing dependencies with uv..."
Push-Location $backendRoot
try {
    uv sync --dev
    Assert-ExitCode -Code $LASTEXITCODE -Step "uv sync --dev"

    # Avoid remote model source checks during local dev startup.
    $env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"

    Write-Host "[3/4] Running OCR preflight (required)..."
    uv run python -c "import paddle; import paddleocr; import chardet; print('OCR OK')"
    Assert-ExitCode -Code $LASTEXITCODE -Step "OCR preflight"

    Write-Host "[4/4] Starting FastAPI with debug and access logs..."
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port $port --access-log --log-level debug
    Assert-ExitCode -Code $LASTEXITCODE -Step "uvicorn"
}
finally {
    Pop-Location
}
