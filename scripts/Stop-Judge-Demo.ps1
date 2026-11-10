$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $repo '.venv\Scripts\python.exe'
$tunnelPath = Join-Path $repo 'outputs\judge-tools\cloudflared.exe'
$targets = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq 'python.exe' -and $_.CommandLine -match [regex]::Escape($repo) -and ($_.CommandLine -match 'web\.judge_demo:create_app|scripts[\\/]judge_demo_start\.py')) -or
    ($_.ExecutablePath -eq $tunnelPath -and $_.CommandLine -match 'http://127\.0\.0\.1:7861')
}
foreach ($process in $targets) { Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue }
Write-Host 'Judge demo stopped. Personal app and saved data are unchanged.'
