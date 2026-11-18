$ErrorActionPreference = 'Continue'
$env:HTTPS_PROXY = 'http://127.0.0.1:7897'
$env:HTTP_PROXY = 'http://127.0.0.1:7897'
$root = 'D:\rob-memory\outputs\go2_edu_research_20261109'
Set-Location $root
if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
    python -m venv "$root\.venv"
}
$py = "$root\.venv\Scripts\python.exe"
& $py -m pip install -U pip wheel 2>&1 | Select-Object -Last 2
& $py -m pip install cyclonedds==0.10.2 2>&1 | Select-Object -Last 4
if (-not (Test-Path "$root\unitree_sdk2_python")) {
    git clone --depth 1 https://github.com/unitreerobotics/unitree_sdk2_python.git "$root\unitree_sdk2_python" 2>&1 | Select-Object -Last 3
}
Set-Location "$root\unitree_sdk2_python"
& $py -m pip install -e . 2>&1 | Select-Object -Last 6
& $py -c "import unitree_sdk2py, cyclonedds; print('import ok')" 2>&1 | Select-Object -Last 3
