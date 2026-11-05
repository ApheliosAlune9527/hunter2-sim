param(
    [Parameter(Mandatory=$true)][string]$RobotIp,
    [string]$Destination = 'F:\rob-memory\maps\lab_20261011'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = 'utf-8'
if ($RobotIp -notmatch '^[A-Za-z0-9.-]+$') { throw '主机地址格式不正确' }
$hzRemote = "car@$RobotIp"
$hzHost = & ssh $hzRemote hostname
if ($LASTEXITCODE -ne 0 -or (($hzHost -join "").Trim() -ne 'car-NUC15JNKU7X4')) {
    throw 'SSH 未连接到预期的小车，停止下载'
}
$hzMetadataText = & ssh $hzRemote 'cat /home/car/hz_ws/maps/latest_export.json'
if ($LASTEXITCODE -ne 0) { throw '找不到本次导出记录，请先在小车上执行 pack' }
$hzMetadata = ($hzMetadataText -join "`n") | ConvertFrom-Json
if ($hzMetadata.format -ne 'hz_mapping_pcd_v1' -or $hzMetadata.run_name -notmatch '^lab_[0-9_]+$' -or $hzMetadata.sha256 -notmatch '^[a-f0-9]{64}$') {
    throw '地图导出记录格式不正确'
}
$hzExpectedPath = "/home/car/hz_ws/maps/$($hzMetadata.run_name).tar.gz"
if ($hzMetadata.archive_path -ne $hzExpectedPath) { throw '地图归档路径不正确' }
if (-not (Test-Path -LiteralPath $Destination)) { New-Item -ItemType Directory -Path $Destination | Out-Null }
$hzArchive = Join-Path $Destination "$($hzMetadata.run_name).tar.gz"
if (Test-Path -LiteralPath $hzArchive) { throw "本地归档已存在，不覆盖：$hzArchive" }
& scp "${hzRemote}:$hzExpectedPath" $hzArchive
if ($LASTEXITCODE -ne 0) { throw '传输未完成；保留小车原文件' }
$hzHash = (Get-FileHash -LiteralPath $hzArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hzHash -ne $hzMetadata.sha256) { throw '传输校验失败，不解包；保留小车原文件' }
$hzPython = (Get-Command python.exe -ErrorAction Stop).Source
$hzPcdTool = Join-Path $PSScriptRoot 'pcd_export.py'
& $hzPython -B $hzPcdTool unpack $hzArchive $Destination --sha256 $hzMetadata.sha256
if ($LASTEXITCODE -ne 0) { throw '解包或点云检查未通过' }
$hzLocalRun = Join-Path $Destination $hzMetadata.run_name
& $hzPython -B $hzPcdTool merge (Join-Path $hzLocalRun 'pcd') (Join-Path $hzLocalRun 'merged')
if ($LASTEXITCODE -ne 0) { throw '地图合并未完成；原始分批 PCD 和归档仍保留' }
Write-Host "下载、SHA256 校验和合并完成：$hzLocalRun\merged"
Write-Host 'map_raw.pcd 保留原始点；map_preview_015m.pcd 每 0.15m 网格保留一个点，用于预览。'
