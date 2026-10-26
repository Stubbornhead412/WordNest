# 一键启动 WordNest（Docker Desktop）
# 用法：在 VSCode 终端或 PowerShell 中执行  .\start-wordnest.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host "==> 检查 Docker 是否在运行..." -ForegroundColor Cyan
$ready = $false
try { docker info --format '{{.ServerVersion}}' | Out-Null; $ready = $true } catch { $ready = $false }

if (-not $ready) {
    Write-Host "Docker 未启动，正在尝试启动 Docker Desktop..." -ForegroundColor Yellow
    $exe = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($exe) { Start-Process $exe } else { Write-Host "找不到 Docker Desktop，请手动从开始菜单启动。" -ForegroundColor Red }

    Write-Host "等待 Docker 引擎就绪（最多 180 秒）..."
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 2
        try { docker info --format '{{.ServerVersion}}' | Out-Null; $ready = $true; break } catch { }
    }
}

if (-not $ready) { Write-Host "Docker 引擎仍不可用，请手动启动 Docker Desktop 后重试。" -ForegroundColor Red; exit 1 }
Write-Host "Docker 已就绪。" -ForegroundColor Green

Write-Host "==> 构建并启动容器..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Write-Host "启动失败，请检查上方输出。" -ForegroundColor Red; exit $LASTEXITCODE }

Write-Host "==> 等待服务响应..." -ForegroundColor Cyan
$port = if ($env:WORDNEST_PORT) { $env:WORDNEST_PORT } else { '5000' }
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { break }
    } catch { }
}

docker compose ps
Write-Host ""
Write-Host "WordNest 已启动： http://localhost:$port" -ForegroundColor Green
try { Start-Process "http://localhost:$port" } catch { Write-Host "（自动打开浏览器失败，请手动访问上面的地址）" -ForegroundColor Yellow }
exit 0
