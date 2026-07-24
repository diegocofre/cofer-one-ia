param(
    [string]$Model,
    [switch]$Remote
)

. (Join-Path $PSScriptRoot "_common.ps1")

$facade = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
$facadeNames = @($facade.models | ForEach-Object { $_.name })

if ($facadeNames.Count -eq 0) {
    Write-Host "Facade is healthy but no logical models are configured."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Model)) {
    if ($Remote) {
        $Model = $facadeNames | Where-Object { $_ -match '^openrouter-' } | Select-Object -First 1
        if (-not $Model) {
            throw "No OpenRouter logical model is available. Pass -Model explicitly."
        }
    } else {
        $physical = Invoke-RestMethod -Uri "http://127.0.0.1:11435/api/tags" -TimeoutSec 10
        $localNames = @($physical.models | ForEach-Object { if ($_.name) { $_.name } else { $_.model } })
        $Model = $facadeNames | Where-Object { $localNames -contains $_ } | Select-Object -First 1
        if (-not $Model) {
            Write-Host "No local chat model is available for a cost-free smoke test."
            Write-Host "Use .\scripts\smoke-test.ps1 -Remote or -Model <logical-model> intentionally."
            exit 0
        }
    }
}

if ($facadeNames -notcontains $Model) {
    throw "Model '$Model' is not present in the facade /api/tags catalog."
}

$payload = @{
    model = $Model
    stream = $false
    messages = @(
        @{ role = "user"; content = "Reply with exactly: OK" }
    )
} | ConvertTo-Json -Depth 8

$result = Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:11434/api/chat" `
    -ContentType "application/json" `
    -Body $payload `
    -TimeoutSec 180

if (-not $result.done) { throw "Response did not contain done=true." }

$content = [string]$result.message.content
if ($content.Trim() -ne "OK") {
    throw "Model completed but smoke response was not exactly 'OK'. Response: $content"
}

Write-Host "[OK] End-to-end model: $Model" -ForegroundColor Green
Write-Host "Response: $content"
