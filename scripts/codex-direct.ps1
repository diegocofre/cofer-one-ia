param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CodexArguments)
. (Join-Path $PSScriptRoot "_common.ps1")
& (Join-Path $PSScriptRoot "codex-direct-setup.ps1")
& codex --profile cofer-direct @CodexArguments
exit $LASTEXITCODE
