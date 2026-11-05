param([Parameter(Mandatory=$true)][string]$Directory)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$hzResults = @()
foreach ($hzFile in (Get-ChildItem -LiteralPath $Directory -Filter *.ps1)) {
    $hzTokens = $null
    $hzErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($hzFile.FullName, [ref]$hzTokens, [ref]$hzErrors) | Out-Null
    if (@($hzErrors).Count -gt 0) { throw ($hzErrors | Out-String) }
    $hzResults += @{ file=$hzFile.Name; errors=0 }
}
@{ version=$PSVersionTable.PSVersion.ToString(); results=$hzResults } | ConvertTo-Json -Depth 4 -Compress
