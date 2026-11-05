param(
    [string]$RobotIp,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding

$hzPackage = Join-Path $PSScriptRoot 'hz_mapping_tools.zip'
$hzChecksum = Join-Path $PSScriptRoot 'hz_mapping_tools.zip.sha256'
if (-not (Test-Path -LiteralPath $hzPackage -PathType Leaf) -or -not (Test-Path -LiteralPath $hzChecksum -PathType Leaf)) {
    throw '请保留完整交付目录：缺少安装包或 SHA256 文件。'
}
$hzHashLine = (Get-Content -LiteralPath $hzChecksum -Raw -Encoding UTF8).Trim()
if ($hzHashLine -notmatch '^([a-fA-F0-9]{64})  hz_mapping_tools\.zip$') {
    throw '安装包 SHA256 文件格式错误。'
}
$hzExpectedHash = $Matches[1].ToLowerInvariant()
$hzActualHash = (Get-FileHash -LiteralPath $hzPackage -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hzActualHash -ne $hzExpectedHash) { throw '本地安装包 SHA256 校验失败，停止上传。' }
Get-Command ssh.exe,scp.exe -ErrorAction Stop | Out-Null
if ($CheckOnly) {
    Write-Host "本地安装包 SHA256 校验通过：$hzExpectedHash"
    Write-Host '离线检查结束。'
    return
}

if ([string]::IsNullOrWhiteSpace($RobotIp)) { $RobotIp = Read-Host '输入当前连接小车使用的 IP' }
if ($RobotIp -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$') { throw '请输入 IP 或主机名，地址中不带端口和空格。' }
$hzRemote = "car@$RobotIp"
$hzHost = & ssh.exe -o ConnectTimeout=10 $hzRemote hostname
if ($LASTEXITCODE -ne 0 -or (($hzHost -join '').Trim() -ne 'car-NUC15JNKU7X4')) {
    throw '没有连到指定的小车，停止安装。'
}
$hzPreflight = 'test "$(id -un)" = car && test -d /home/car/hz_ws && test ! -L /home/car/hz_ws && test "$(readlink -f /home/car/hz_ws)" = /home/car/hz_ws'
& ssh.exe -o ConnectTimeout=10 $hzRemote $hzPreflight
if ($LASTEXITCODE -ne 0) { throw '小车账户或个人工作区路径不符合预期，停止安装。' }

$hzToken = [Guid]::NewGuid().ToString('N')
$hzUpload = "/home/car/hz_ws/.hz_mapping_upload_${hzToken}.zip"
& scp.exe -o ConnectTimeout=10 $hzPackage "${hzRemote}:$hzUpload"
if ($LASTEXITCODE -ne 0) { throw "上传未完成。只可能留有本次临时包：$hzUpload" }
& ssh.exe -o ConnectTimeout=10 $hzRemote "python3 -B $hzUpload --sha256 $hzExpectedHash"
if ($LASTEXITCODE -ne 0) { throw '安装未通过。保留终端输出；已有工具和地图没有被替换。' }

Write-Host '文件安装完成，开始小车端环境预检。'
$hzDoctor = 'bash -c ''source /home/car/hz_ws/hz_mapping_tools/hz_env.sh && ros2 launch "$hzLaunch" role:=doctor'''
& ssh.exe -o ConnectTimeout=10 $hzRemote $hzDoctor
if ($LASTEXITCODE -ne 0) {
    throw '文件已安装，但小车端预检未通过。请保留上述输出，处理具体问题后重新运行同一安装命令核验。'
}
Write-Host '安装及环境预检完成。接下来在小车 Ubuntu 终端按“建图使用说明.txt”操作。'
