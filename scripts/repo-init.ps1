. (Join-Path $PSScriptRoot "_common.ps1")

Require-Command "git"
$null = Get-PythonInvocation

Push-Location $Root
try {
    if (-not (Test-Path ".git")) {
        & git init -b main
        if ($LASTEXITCODE -ne 0) { throw "git init failed." }
    }

    foreach ($path in @("upstream/headroom", "upstream/litellm")) {
        if ((Test-Path $path) -and -not (Test-Path ".gitmodules")) {
            throw "Existing nested checkout '$path' found. Remove it before registering true submodules."
        }
    }

    Invoke-Python "tools/upstreams.py" "init"
    Write-Host ""
    Write-Host "Submodules initialized. Verify with:" -ForegroundColor Green
    Write-Host "  git submodule status"
    Write-Host "  git status"
} finally {
    Pop-Location
}
