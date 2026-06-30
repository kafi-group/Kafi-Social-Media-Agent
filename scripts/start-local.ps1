# Start Kafi Social Agent locally (Windows)
# Usage: powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "venv\Scripts\python.exe"
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

if (-not (Test-Path $Python)) {
    Write-Error "venv not found at $Python. Create it and run: pip install -r backend/requirements.txt"
    exit 1
}

# Avoid duplicate backends on :8000 (causes 404s / wrong OAuth code / wrong channel).
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        $procId = $_.OwningProcess
        Write-Host "Stopping existing backend on port 8000 (PID $procId)..."
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 1

Write-Host "Starting backend on http://127.0.0.1:8000 ..."
Start-Process -FilePath $Python -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" -WorkingDirectory $Backend

Start-Sleep -Seconds 3

Write-Host "Starting frontend on http://localhost:3000 ..."
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory $Frontend

Write-Host ""
Write-Host "Backend:  http://127.0.0.1:8000/api/v1/health"
Write-Host "Frontend: http://localhost:3000 (or 3001 if 3000 is busy)"
Write-Host "YouTube OAuth (local): http://localhost:8000/api/v1/auth/youtube"
Write-Host "LinkedIn OAuth (local): http://localhost:8000/api/v1/auth/linkedin"
Write-Host "Meta OAuth (local):    http://localhost:8000/api/v1/auth/meta"
