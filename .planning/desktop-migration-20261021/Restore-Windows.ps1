param()
$ErrorActionPreference = 'Stop'
$expectedProfile = 'C:\Users\ASUS'
$targetProject = 'D:\rob-memory'
$actualProfile = [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')
if ($actualProfile -ine $expectedProfile) {
    throw "本包按 C:\Users\ASUS 和 D:\rob-memory 准备。当前用户目录为 $actualProfile，请勿在旧电脑运行。"
}
if (Get-Process -Name Codex,ChatGPT -ErrorAction SilentlyContinue) {
    throw '请先彻底退出 Codex/ChatGPT 桌面应用及 Codex 终端，再运行此脚本。脚本不会自动结束你的程序。'
}
if (-not (Test-Path -LiteralPath 'D:\')) { throw '未找到台式机 D 盘。' }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$packageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
if ($packageRoot.StartsWith($targetProject + '\', [StringComparison]::OrdinalIgnoreCase) -or $packageRoot -ieq $targetProject) {
    throw '请把迁移包解压到 D:\迁移接收 等独立目录，不能放在待恢复的 D:\rob-memory 里面。'
}
$manifest = Get-Content -LiteralPath (Join-Path $packageRoot 'MANIFEST.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ((Get-PSDrive D).Free -lt ($manifest.project_bytes + 1GB)) { throw 'D 盘剩余空间不足以复制项目，请先留出足够空间。' }
if ((Get-PSDrive C).Free -lt ($manifest.profile_bytes + 512MB)) { throw 'C 盘剩余空间不足以恢复 Codex 数据。' }
$backups = [Collections.Generic.List[string]]::new()
function Copy-MigrationTree([string]$source, [string]$destination, [bool]$backupExisting = $true) {
    $sourceFull = [IO.Path]::GetFullPath($source)
    $destinationFull = [IO.Path]::GetFullPath($destination).TrimEnd('\')
    if (-not $sourceFull.StartsWith($packageRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '源路径超出了已解压的迁移包。' }
    $allowed = @($targetProject, (Join-Path $actualProfile '.codex'), (Join-Path $actualProfile '.agents'))
    if ($destinationFull -notin $allowed) { throw "不允许修改此目标：$destinationFull" }
    if (-not (Test-Path -LiteralPath $sourceFull -PathType Container)) { throw "包内缺少目录：$sourceFull" }
    $backupPath = $null
    if ($backupExisting -and (Test-Path -LiteralPath $destinationFull)) {
        $existing = Get-Item -LiteralPath $destinationFull -Force
        if ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "目标是链接目录，请先人工核对：$destinationFull" }
        $backupPath = $destinationFull + '.before-migration-' + $stamp
        if (Test-Path -LiteralPath $backupPath) { throw "备份目录已存在：$backupPath" }
        # Both resolved paths have been checked against the explicit migration targets.
        Move-Item -LiteralPath $destinationFull -Destination $backupPath
        $backups.Add($backupPath)
    }
    New-Item -ItemType Directory -Path $destinationFull -Force | Out-Null
    & robocopy.exe $sourceFull $destinationFull /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XJ /NP /NFL /NDL | Out-Host
    if ($LASTEXITCODE -ge 8) { throw "复制失败（$LASTEXITCODE）：$destinationFull。已有备份保留在 $backupPath" }
    return $backupPath
}
Write-Host '正在恢复项目到 D:\rob-memory……'
$projectBackup = Copy-MigrationTree (Join-Path $packageRoot 'rob-memory') $targetProject
Write-Host '正在恢复 Codex 对话、附件、配置和技能……'
$codexBackup = Copy-MigrationTree (Join-Path $packageRoot 'user-profile\.codex') (Join-Path $actualProfile '.codex')
if ($codexBackup) {
    foreach ($name in @('auth.json','cap_sid','installation_id')) {
        $existingFile = Join-Path $codexBackup $name
        if (Test-Path -LiteralPath $existingFile -PathType Leaf) {
            Copy-Item -LiteralPath $existingFile -Destination (Join-Path $actualProfile ('.codex\' + $name))
        }
    }
}
$agentsBackup = Copy-MigrationTree (Join-Path $packageRoot 'user-profile\.agents') (Join-Path $actualProfile '.agents')
$artifactSource = Join-Path $packageRoot 'app-supplement\artifact-sessions'
if (Test-Path -LiteralPath $artifactSource -PathType Container) {
    $artifactTarget = Join-Path $env:APPDATA 'Codex\web\Codex\artifact-sessions'
    New-Item -ItemType Directory -Path $artifactTarget -Force | Out-Null
    & robocopy.exe $artifactSource $artifactTarget /E /COPY:DAT /R:1 /W:1 /XJ /NP /NFL /NDL /XC /XN /XO
    if ($LASTEXITCODE -ge 8) { throw '应用画布补充数据复制失败；项目和 Codex 主数据已复制，请保留本包。' }
}
$latestPath = Join-Path $actualProfile '.codex\plugins\cache\openai-bundled\chrome\latest'
$versionPath = Join-Path $actualProfile '.codex\plugins\cache\openai-bundled\chrome\26.1013.40934'
if ((Test-Path -LiteralPath $versionPath) -and -not (Test-Path -LiteralPath $latestPath)) {
    New-Item -ItemType Junction -Path $latestPath -Target $versionPath | Out-Null
}
$receipt = [ordered]@{time=(Get-Date).ToString('o');project=$targetProject;profile=$actualProfile;backups=@($backups);ubuntuImported=$false}
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $packageRoot ('restore-receipt-' + $stamp + '.json')) -Encoding UTF8
Write-Host 'Windows 文件恢复完成。请用原账号登录 Codex，检查旧对话与附件。'
Write-Host 'Ubuntu 尚未导入；需要时按 README_先读我.txt 的第 4 步操作。'
Write-Host '项目中的历史文档和仿真脚本保持原样；F 盘路径的后续适配请阅读说明。'
if ($backups.Count) { Write-Host ('原有台式机数据的备份：' + ($backups -join '；')) }
