param([switch]$Demo)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path $python) -or -not (Test-Path 'frontend/node_modules')) { throw 'Run setup.ps1 first.' }
$env:DEMO_MODE = if ($Demo) { 'true' } else { 'false' }
$backend = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory (Join-Path $PSScriptRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot 'backend/server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'backend/server-error.log')
try {
    $ready = $false
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        if ($backend.HasExited) { throw 'Backend failed to start. Check backend/server-error.log.' }
        try { $null = Invoke-RestMethod 'http://127.0.0.1:8000/api/health'; $ready=$true; break }
        catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'Backend startup timed out.' }
    Write-Host 'TripBudget: http://127.0.0.1:5173  |  API docs: http://127.0.0.1:8000/docs'
    Push-Location frontend
    try { npm.cmd run dev } finally { Pop-Location }
} finally { if (-not $backend.HasExited) { Stop-Process -Id $backend.Id } }
