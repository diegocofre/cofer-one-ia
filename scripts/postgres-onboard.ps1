param(
    [ValidateSet("configure", "status", "disable", "verify")]
    [string]$Action = "configure",
    [switch]$SkipTest
)

. (Join-Path $PSScriptRoot "_common.ps1")

$args = @("tools/postgres_onboard.py", $Action, "--env", ".env")
if ($SkipTest) { $args += "--skip-test" }

Push-Location $Root
try {
    Invoke-Python @args
} finally {
    Pop-Location
}
