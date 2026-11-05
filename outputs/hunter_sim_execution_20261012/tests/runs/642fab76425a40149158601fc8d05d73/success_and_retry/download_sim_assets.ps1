param(
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$RobotIp,
    [string]$Destination
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding

if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = Join-Path $PSScriptRoot 'references\archives'
}

if ($RobotIp -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$') {
    throw '小车地址格式不正确；请使用之前传输点云时的 IP 地址。'
}
$hzManifestPath = Join-Path $PSScriptRoot 'references\asset_transfer_manifest_20261012.json'
$hzManifest = Get-Content -LiteralPath $hzManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($hzManifest.expected_robot_hostname -ne 'car-NUC15JNKU7X4' -or $hzManifest.ssh_user -ne 'car' -or @($hzManifest.archives).Count -ne 2) {
    throw '参考资料清单格式不正确。'
}
$hzDestinationRoot = [IO.Path]::GetFullPath($Destination)
if ((Test-Path -LiteralPath $hzDestinationRoot) -and -not (Test-Path -LiteralPath $hzDestinationRoot -PathType Container)) {
    throw '下载目录指向了一个已有文件，请换用独立目录。'
}
$hzEntries = @()
$hzSeenNames = @{}
foreach ($hzAsset in $hzManifest.archives) {
    if ($hzAsset.filename -notin @('hunter_reference.tar.gz', 'realsense_description_reference.tar.gz') -or
        $hzSeenNames.ContainsKey($hzAsset.filename) -or
        $hzAsset.sha256 -notmatch '^[a-f0-9]{64}$' -or
        $hzAsset.robot_path -notmatch '^/home/car/hz_sim_(assets|camera)_[0-9]{8}_[A-Za-z0-9]{6}/[A-Za-z0-9._-]+\.tar\.gz$' -or
        -not $hzAsset.robot_path.EndsWith('/' + $hzAsset.filename)) {
        throw '参考资料清单中的文件路径或校验值不正确。'
    }
    $hzSeenNames[$hzAsset.filename] = $true
    $hzLocalPath = Join-Path $hzDestinationRoot $hzAsset.filename
    $hzVerified = $false
    if (Test-Path -LiteralPath $hzLocalPath) {
        $hzExistingHash = (Get-FileHash -LiteralPath $hzLocalPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hzExistingHash -ne $hzAsset.sha256) {
            throw "已存在文件的校验值不符，保留原文件并停止：$hzLocalPath"
        }
        $hzVerified = $true
    }
    $hzEntries += [PSCustomObject]@{ Asset = $hzAsset; LocalPath = $hzLocalPath; Verified = $hzVerified }
}

$hzPending = @($hzEntries | Where-Object { -not $_.Verified })
if ($hzPending.Count -gt 0) {
    Get-Command ssh, scp -ErrorAction Stop | Out-Null
    $hzRemote = "car@$RobotIp"
    $hzHostname = & ssh -o ConnectTimeout=8 -o ConnectionAttempts=1 $hzRemote hostname
    if ($LASTEXITCODE -ne 0 -or (($hzHostname -join '').Trim() -ne $hzManifest.expected_robot_hostname)) {
        throw 'SSH 连接失败或主机名不符；停止下载，请把错误提示发来。'
    }
    if (-not (Test-Path -LiteralPath $hzDestinationRoot)) {
        New-Item -ItemType Directory -Path $hzDestinationRoot | Out-Null
    }
    foreach ($hzEntry in $hzPending) {
        $hzPartialPath = $hzEntry.LocalPath + '.' + [guid]::NewGuid().ToString('N') + '.partial'
        Write-Host "正在下载：$($hzEntry.Asset.filename)"
        & scp -o ConnectTimeout=8 -o ConnectionAttempts=1 "${hzRemote}:$($hzEntry.Asset.robot_path)" $hzPartialPath
        if ($LASTEXITCODE -ne 0) {
            throw "传输失败，停止下载；如有未完成文件则保留在：$hzPartialPath"
        }
        $hzReceivedHash = (Get-FileHash -LiteralPath $hzPartialPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hzReceivedHash -ne $hzEntry.Asset.sha256) {
            throw "校验失败，保留待检查文件：$hzPartialPath"
        }
        Move-Item -LiteralPath $hzPartialPath -Destination $hzEntry.LocalPath -ErrorAction Stop
        $hzEntry.Verified = $true
    }
}
foreach ($hzEntry in $hzEntries) {
    Write-Host "SHA256 校验通过：$($hzEntry.Asset.filename)"
}
Write-Host "两个参考包已就绪：$hzDestinationRoot"
