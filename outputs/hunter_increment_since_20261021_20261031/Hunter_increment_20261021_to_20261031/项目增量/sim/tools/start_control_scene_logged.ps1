[CmdletBinding(PositionalBinding=$false)]
param([switch]$Check)

# Compatibility name: the default logged entry now opens the full model.
& (Join-Path $PSScriptRoot 'start_hunter_full_scene.ps1') -Check:$Check
exit $LASTEXITCODE
