. (Join-Path $PSScriptRoot "_common.ps1")

Write-Step "Checking pinned upstreams"
Push-Location $Root
try {
    Invoke-Python "tools/upstreams.py" "fetch"
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Pins are NOT changed automatically."
Write-Host "Review release notes, edit upstreams.lock.json and .env.example intentionally,"
Write-Host "then test source mode and smoke tests before committing an upgrade."
Write-Host ""
Write-Host "Runtime images currently configured:"
Write-Host "  Headroom: $(Get-DotEnvValue 'HEADROOM_IMAGE')"
Write-Host "  LiteLLM:  $(Get-DotEnvValue 'LITELLM_IMAGE')"
