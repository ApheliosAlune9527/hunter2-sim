param(
    [string]$ScriptPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'download_sim_assets.ps1')
)
$ErrorActionPreference = 'Stop'

function Assert-TransferCheck([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "检查失败：$Message" }
}

Assert-TransferCheck (Test-Path -LiteralPath $ScriptPath) '下载脚本尚未实现'
$testRunRoot = Join-Path $PSScriptRoot ('runs\' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRunRoot | Out-Null

# Only local fixtures are used. These functions prevent real SSH or SCP calls.
function global:ssh {
    Assert-TransferCheck ($args[-1] -eq 'hostname') '仅允许查询主机名'
    $global:hzTransferTestSshCalls++
    $global:LASTEXITCODE = 0
    $global:hzTransferTestHostname
}
function global:scp {
    $global:hzTransferTestCopyCalls++
    if ($global:hzTransferTestCopyFails) {
        $global:LASTEXITCODE = 1
        return
    }
    $testSourceName = [IO.Path]::GetFileName(($args[-2] -split ':', 2)[1])
    $testCopyDestination = $args[-1]
    if ($global:hzTransferTestCorruptCopy) {
        [IO.File]::WriteAllText($testCopyDestination, 'damaged transfer payload')
    } else {
        Copy-Item -LiteralPath (Join-Path $global:hzTransferTestFixtureDir $testSourceName) -Destination $testCopyDestination
    }
    $global:LASTEXITCODE = 0
}

function New-TransferScenario([string]$Name) {
    $scenarioRoot = Join-Path $testRunRoot $Name
    $scenarioReferences = Join-Path $scenarioRoot 'references'
    $scenarioFixtures = Join-Path $scenarioRoot 'fixtures'
    New-Item -ItemType Directory -Path $scenarioReferences, $scenarioFixtures | Out-Null
    $scenarioScript = Join-Path $scenarioRoot 'download_sim_assets.ps1'
    Copy-Item -LiteralPath $ScriptPath -Destination $scenarioScript
    $scenarioAssets = @(
        @{ filename = 'hunter_reference.tar.gz'; robot_path = '/home/car/hz_sim_assets_20261012_pT9x29/hunter_reference.tar.gz' },
        @{ filename = 'realsense_description_reference.tar.gz'; robot_path = '/home/car/hz_sim_camera_20261012_FPDj8X/realsense_description_reference.tar.gz' }
    )
    foreach ($scenarioAsset in $scenarioAssets) {
        $fixturePath = Join-Path $scenarioFixtures $scenarioAsset.filename
        [IO.File]::WriteAllText($fixturePath, "local test payload: $($scenarioAsset.filename)")
        $scenarioAsset.sha256 = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $scenarioManifest = @{ expected_robot_hostname = 'car-NUC15JNKU7X4'; ssh_user = 'car'; archives = $scenarioAssets }
    $scenarioManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $scenarioReferences 'asset_transfer_manifest_20261012.json') -Encoding UTF8
    $global:hzTransferTestHostname = 'car-NUC15JNKU7X4'
    $global:hzTransferTestFixtureDir = $scenarioFixtures
    $global:hzTransferTestSshCalls = 0
    $global:hzTransferTestCopyCalls = 0
    $global:hzTransferTestCopyFails = $false
    $global:hzTransferTestCorruptCopy = $false
    [PSCustomObject]@{ Script = $scenarioScript; Destination = (Join-Path $scenarioRoot 'download'); Assets = $scenarioAssets }
}

function Invoke-ExpectTransferFailure($Scenario, [string]$ErrorPattern) {
    $failureText = ''
    try {
        & $Scenario.Script -RobotIp '127.0.0.1' -Destination $Scenario.Destination
    } catch { $failureText = $_.Exception.Message }
    Assert-TransferCheck ($failureText -match $ErrorPattern) "应因 $ErrorPattern 停止，实际：$failureText"
}

$scenario = New-TransferScenario 'default_destination'
$savedTestErrorAction = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    $externalStartupOutput = (& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $scenario.Script -RobotIp 'invalid address' 2>&1 | Out-String)
    $externalStartupCode = $LASTEXITCODE
} finally { $ErrorActionPreference = $savedTestErrorAction }
Assert-TransferCheck ($externalStartupCode -ne 0 -and $externalStartupOutput -match '小车地址格式不正确') "外部 -File 启动应进入地址校验，不能因默认目录报错：$externalStartupOutput"
& $scenario.Script -RobotIp '127.0.0.1'
$defaultScenarioDestination = Join-Path (Split-Path $scenario.Script -Parent) 'references\archives'
foreach ($asset in $scenario.Assets) {
    $defaultReceivedHash = (Get-FileHash -LiteralPath (Join-Path $defaultScenarioDestination $asset.filename) -Algorithm SHA256).Hash.ToLowerInvariant()
    Assert-TransferCheck ($defaultReceivedHash -eq $asset.sha256) '默认目录应位于下载脚本目录内'
}
# Both fixture archives now exist with valid checksums, so this external launch skips SSH/SCP.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $scenario.Script -RobotIp '127.0.0.1'
Assert-TransferCheck ($LASTEXITCODE -eq 0) '外部 -File 启动且省略下载目录应成功'
Write-Host 'PASS 默认目录与外部 -File 启动'

$scenario = New-TransferScenario 'success_and_retry'
& $scenario.Script -RobotIp '127.0.0.1' -Destination $scenario.Destination
foreach ($asset in $scenario.Assets) {
    $receivedHash = (Get-FileHash -LiteralPath (Join-Path $scenario.Destination $asset.filename) -Algorithm SHA256).Hash.ToLowerInvariant()
    Assert-TransferCheck ($receivedHash -eq $asset.sha256) '下载结果应与源数据一致'
}
Assert-TransferCheck ($global:hzTransferTestCopyCalls -eq 2) '应下载两个包'
& $scenario.Script -RobotIp '127.0.0.1' -Destination $scenario.Destination
Assert-TransferCheck ($global:hzTransferTestCopyCalls -eq 2) '已校验的包不应再次下载'
Write-Host 'PASS 下载校验与重复运行'

$scenario = New-TransferScenario 'wrong_host'
$global:hzTransferTestHostname = 'other-computer'
Invoke-ExpectTransferFailure $scenario '主机名'
Assert-TransferCheck ($global:hzTransferTestCopyCalls -eq 0) '主机错误时不应下载'
Write-Host 'PASS 主机名不符时停止'

$scenario = New-TransferScenario 'existing_conflict'
New-Item -ItemType Directory -Path $scenario.Destination | Out-Null
$existingPath = Join-Path $scenario.Destination 'hunter_reference.tar.gz'
[IO.File]::WriteAllText($existingPath, 'keep existing file')
Invoke-ExpectTransferFailure $scenario '已存在文件'
Assert-TransferCheck ([IO.File]::ReadAllText($existingPath) -eq 'keep existing file') '不得覆盖既有文件'
Assert-TransferCheck ($global:hzTransferTestCopyCalls -eq 0) '发现冲突后不应下载'
Write-Host 'PASS 保留既有冲突文件'

$scenario = New-TransferScenario 'checksum_failure'
$global:hzTransferTestCorruptCopy = $true
Invoke-ExpectTransferFailure $scenario '校验失败'
Assert-TransferCheck (-not (Test-Path -LiteralPath (Join-Path $scenario.Destination 'hunter_reference.tar.gz'))) '损坏数据不得作为正式文件保存'
Assert-TransferCheck ($global:hzTransferTestCopyCalls -eq 1) '校验失败后应停止后续传输'
Write-Host 'PASS 损坏传输被校验拦截'

$scenario = New-TransferScenario 'copy_failure'
$global:hzTransferTestCopyFails = $true
Invoke-ExpectTransferFailure $scenario '传输失败'
Assert-TransferCheck (-not (Test-Path -LiteralPath (Join-Path $scenario.Destination 'hunter_reference.tar.gz'))) '失败传输不得生成正式文件'
Write-Host 'PASS 传输失败时停止'
Write-Host '6 项离线检查通过；没有连接真实小车。'
