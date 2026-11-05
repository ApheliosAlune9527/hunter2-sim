[CmdletBinding(PositionalBinding=$false)]
param([switch]$Check)

$hzSavedConsoleEncoding = [Console]::OutputEncoding
$hzLauncherExitCode = 1
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $hzWslExecutable = Join-Path $env:WINDIR 'System32\wsl.exe'
    $hzLinuxLauncher = '/mnt/d/rob-memory/sim/tools/start_hunter_full_scene.bash'
    if ($Check) {
        & $hzWslExecutable -d Ubuntu-22.04 -u aphelios --exec /bin/bash $hzLinuxLauncher --check
    } else {
        & $hzWslExecutable -d Ubuntu-22.04 -u aphelios --exec /bin/bash $hzLinuxLauncher
    }
    $hzLauncherExitCode = $LASTEXITCODE
} finally {
    [Console]::OutputEncoding = $hzSavedConsoleEncoding
}
exit $hzLauncherExitCode
