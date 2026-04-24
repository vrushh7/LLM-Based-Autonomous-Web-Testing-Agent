param(
    [switch]$Reinstall
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvPy = Join-Path $root '.venv\Scripts\python.exe'

function Ensure-Venv {
    if (-not (Test-Path $venvPy)) {
        Write-Output "Creating virtualenv..."
        python -m venv "$root\.venv"
    }
    Write-Output "Ensuring backend dependencies..."
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -r (Join-Path $root 'backend\requirements.txt')
    & $venvPy -m pip install requests pytest
}

if ($Reinstall) { Ensure-Venv }
elseif (-not (Test-Path $venvPy)) { Ensure-Venv }

Write-Output "Starting backend (port 8001) as background job..."
$backendJob = Start-Job -Name ait_backend -ArgumentList $venvPy,$root -ScriptBlock {
    param($venvPath,$rootPath)
    $env:PORT = '8001'
    $env:HOST = '0.0.0.0'
    & $venvPath (Join-Path $rootPath 'backend\main.py')
}

Start-Sleep -Seconds 1

Write-Output "Starting frontend static server (port 8000) as background job..."
$frontendJob = Start-Job -Name ait_frontend -ArgumentList $venvPy,$root -ScriptBlock {
    param($venvPath,$rootPath)
    & $venvPath -m http.server 8000 --directory (Join-Path $rootPath 'frontend')
}

Write-Output "Started jobs: ait_backend (port 8001), ait_frontend (port 8000)."
Write-Output "View jobs: Get-Job | Format-Table -AutoSize"
Write-Output "Stop jobs: Get-Job -Name ait_backend,ait_frontend | Stop-Job"
Write-Output "Open frontend: http://localhost:8000"
Write-Output "Open API docs: http://localhost:8001/docs"
