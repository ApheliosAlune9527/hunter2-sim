[CmdletBinding()]
param([switch]$Check)

# Keep Linux UTF-8 output out of the Windows PowerShell Tee-Object pipeline.
# Console encoding is restored when this personal launcher exits.
$hzSavedConsoleEncoding = [Console]::OutputEncoding
$hzLauncherExitCode = 1
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $hzWslExecutable = Join-Path $env:WINDIR 'System32\wsl.exe'
    $hzLinuxLauncher = '/mnt/f/rob-memory/sim/tools/start_control_scene_logged.bash'
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
