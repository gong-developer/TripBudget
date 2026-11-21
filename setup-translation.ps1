$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$uv = Join-Path $PSScriptRoot '.tools/uv/uv.exe'
$python = Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe'
$translationPython = Join-Path $PSScriptRoot '.tools/libretranslate/.venv/Scripts/python.exe'
if (-not (Test-Path $python)) { throw 'Run setup.ps1 first.' }
if (-not (Test-Path $uv)) { throw 'This setup requires the project-local .tools/uv/uv.exe.' }
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.tools/cache'
if (-not (Test-Path $translationPython)) {
    & $uv venv '.tools/libretranslate/.venv' --python $python
    if ($LASTEXITCODE -ne 0) { throw 'Translation environment creation failed.' }
}
& $uv pip install --python $translationPython 'libretranslate==1.9.6'
if ($LASTEXITCODE -ne 0) { throw 'LibreTranslate installation failed.' }
Write-Host 'Installed. Starting LibreTranslate; first launch downloads English/Korean models. Stop with Ctrl+C.'
& (Join-Path $PSScriptRoot 'start-translation.ps1')
