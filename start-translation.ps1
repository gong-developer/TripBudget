param([switch]$Background)
$ErrorActionPreference = 'Stop'
$translationRoot = Join-Path $PSScriptRoot '.tools/libretranslate'
$executable = Join-Path $translationRoot '.venv/Scripts/libretranslate.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Run setup-translation.ps1 first.' }
try {
    $languages = @(Invoke-RestMethod 'http://127.0.0.1:5000/languages' -TimeoutSec 3)
    if (($languages | Where-Object { $_.code -eq 'en' -and $_.targets -contains 'ko' }).Count -gt 0) {
        Write-Host 'LibreTranslate is already running at http://127.0.0.1:5000'
        return
    }
} catch { }
$env:XDG_DATA_HOME = Join-Path $translationRoot 'data'
$env:XDG_CONFIG_HOME = Join-Path $translationRoot 'config'
$env:XDG_CACHE_HOME = Join-Path $translationRoot 'cache'
$env:PYTHONUNBUFFERED = '1'
$arguments = @('--host','127.0.0.1','--port','5000','--load-only','en,ko','--disable-web-ui','--disable-files-translation')
if ($Background) {
    $process = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $translationRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $translationRoot 'server.log') -RedirectStandardError (Join-Path $translationRoot 'server-error.log')
    try {
        for ($attempt=0; $attempt -lt 90; $attempt++) {
            if ($process.HasExited) { throw 'LibreTranslate failed. Check .tools/libretranslate/server-error.log.' }
            try {
                $languages = @(Invoke-RestMethod 'http://127.0.0.1:5000/languages' -TimeoutSec 2)
                if (($languages | Where-Object { $_.code -eq 'en' -and $_.targets -contains 'ko' }).Count -gt 0) { return $process }
            } catch { }
            Start-Sleep -Milliseconds 500
        }
        throw 'LibreTranslate startup timed out. Run start-translation.ps1 separately to finish downloading models.'
    } catch {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id }
        throw
    }
} else {
    & $executable @arguments
    if ($LASTEXITCODE -ne 0) { throw 'LibreTranslate failed to start.' }
}
