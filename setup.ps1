$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path 'backend/.env')) { Copy-Item 'backend/.env.example' 'backend/.env' }
if (-not (Test-Path 'backend/.venv/Scripts/python.exe')) {
    if (Test-Path '.tools/uv/uv.exe') {
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '.tools/python'
        $env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.tools/cache'
        & '.tools/uv/uv.exe' venv backend/.venv --python 3.12
    } else { python -m venv backend/.venv }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
if (Test-Path '.tools/uv/uv.exe') {
    $env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.tools/cache'
    & '.tools/uv/uv.exe' pip install --python backend/.venv/Scripts/python.exe -r backend/requirements.txt
} else { & 'backend/.venv/Scripts/python.exe' -m pip install -r backend/requirements.txt }
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
Push-Location frontend
try { npm.cmd install; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' } }
finally { Pop-Location }
Write-Host 'Setup complete. Set GEMINI_API_KEY in backend/.env, then run start.ps1.'
