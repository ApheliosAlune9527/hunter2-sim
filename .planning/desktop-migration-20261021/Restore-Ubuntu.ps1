param()
$ErrorActionPreference = 'Stop'
if ($env:USERPROFILE.TrimEnd('\') -ine 'C:\Users\ASUS') { throw '此脚本仅供 ASUS 台式机恢复使用，请勿在旧电脑运行。' }
$vhd = 'D:\rob-memory\wsl\Ubuntu22.04\ext4.vhdx'
if (-not (Test-Path -LiteralPath $vhd -PathType Leaf)) { throw '请先运行 Restore-Windows.ps1，确认 D:\rob-memory 已恢复。' }
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { throw '请先安装 WSL，再按说明重启台式机。' }
$names = @(& wsl.exe --list --quiet 2>$null | ForEach-Object { $_.Replace([string][char]0,'').Trim() })
if ($names -contains 'Ubuntu-22.04') { throw '台式机已有 Ubuntu-22.04。为保护现有环境，本脚本停止；请人工核对，勿卸载已有发行版。' }
& wsl.exe --import-in-place Ubuntu-22.04 $vhd
if ($LASTEXITCODE -ne 0) { throw "Ubuntu 导入失败（$LASTEXITCODE），请保留虚拟磁盘并检查 WSL 安装状态。" }
Write-Host 'Ubuntu 已注册到 D 盘。进入环境的命令：'
Write-Host 'wsl -d Ubuntu-22.04 -u aphelios'
Write-Host '此脚本没有启动 ROS、仿真、底盘或其他机器人程序。'
