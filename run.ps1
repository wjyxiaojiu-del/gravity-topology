# run.ps1 - 启动引力拓扑服务
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Gravity Topology Launcher ===" -ForegroundColor Cyan
Write-Host ""

# 1. 停止占用 8050 端口的旧进程
$port = 8050
$procs = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
if ($procs) {
    foreach ($pid in $procs) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -eq "python") {
            Write-Host "[*] Stopping old python process (PID $pid) on port $port..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force
        }
    }
    Start-Sleep -Seconds 1
}

# 2. 设置编码
$env:PYTHONIOENCODING = "utf-8"

# 3. 加载 .env 文件
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Write-Host "[*] Loading .env file..." -ForegroundColor Gray
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $parts = $line -split "=", 2
            if ($parts.Length -eq 2) {
                $key = $parts[0].Trim()
                $val = $parts[1].Trim()
                [Environment]::SetEnvironmentVariable($key, $val, "Process")
            }
        }
    }
}

# 4. 打印 OAuth 配置状态
Write-Host ""
Write-Host "--- OAuth Config ---" -ForegroundColor Cyan
$appId = [Environment]::GetEnvironmentVariable("ZHIHU_OAUTH_APP_ID", "Process")
$appKey = [Environment]::GetEnvironmentVariable("ZHIHU_OAUTH_APP_KEY", "Process")
$redirectUri = [Environment]::GetEnvironmentVariable("ZHIHU_OAUTH_REDIRECT_URI", "Process")

if ($appId) {
    Write-Host "  ZHIHU_OAUTH_APP_ID     = $appId" -ForegroundColor Green
} else {
    Write-Host "  ZHIHU_OAUTH_APP_ID     = (not set)" -ForegroundColor Red
}

if ($appKey) {
    Write-Host "  ZHIHU_OAUTH_APP_KEY    = $($appKey.Substring(0, [Math]::Min(6, $appKey.Length)))..." -ForegroundColor Green
} else {
    Write-Host "  ZHIHU_OAUTH_APP_KEY    = (not set)" -ForegroundColor Red
}

if ($redirectUri) {
    Write-Host "  ZHIHU_OAUTH_REDIRECT_URI = $redirectUri" -ForegroundColor Green
} else {
    Write-Host "  ZHIHU_OAUTH_REDIRECT_URI = (using default: http://localhost:8050/callback)" -ForegroundColor Yellow
}

$communityKey = [Environment]::GetEnvironmentVariable("ZHIHU_COMMUNITY_APP_KEY", "Process")
if ($communityKey) {
    Write-Host "  ZHIHU_COMMUNITY_APP_KEY = $communityKey" -ForegroundColor Green
} else {
    Write-Host "  ZHIHU_COMMUNITY_APP_KEY = (not set)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "--- Starting server ---" -ForegroundColor Cyan
Write-Host "[OK] Server will run at: http://localhost:8050/" -ForegroundColor Green
Write-Host ""

# 5. 启动 Flask
python app.py
