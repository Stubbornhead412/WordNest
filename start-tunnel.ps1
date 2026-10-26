# 用 Cloudflare 临时隧道把本机 WordNest 暴露到公网（手机用流量也能访问）
#
# 用法：
#   .\start-tunnel.ps1
# 停止：
#   Ctrl+C（隧道随即失效，公网地址作废）
#
# 说明：
#   - 这是"快速隧道"，不需要 Cloudflare 账号，但地址每次启动都会变、没有可用性保证
#   - 关闭窗口 / 按 Ctrl+C 就断开，手机立刻打不开
#   - 暴露公网前请务必在 .env 里设置 WORDNEST_PASSWORD

$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

function Find-Cloudflared {
    $candidates = @(
        (Join-Path (Split-Path $PSScriptRoot -Parent) 'tools\cloudflared.exe'),
        (Join-Path $PSScriptRoot 'tools\cloudflared.exe')
    )
    foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$exe = Find-Cloudflared
if (-not $exe) {
    Write-Host "找不到 cloudflared.exe。" -ForegroundColor Red
    Write-Host "请把 cloudflared.exe 放到 ..\tools\ 目录，或运行：" -ForegroundColor Yellow
    Write-Host "  winget install --id Cloudflare.cloudflared" -ForegroundColor Yellow
    exit 1
}

Write-Host "==> 检查本地服务..." -ForegroundColor Cyan
$ok = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5000/" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) { $ok = $true }
} catch { }

if (-not $ok) {
    Write-Host "本地 http://127.0.0.1:5000 打不开，先启动容器：" -ForegroundColor Red
    Write-Host "  docker compose up -d" -ForegroundColor Yellow
    exit 1
}

# 检查是否已设置访问密码
$envFile = Join-Path $PSScriptRoot '.env'
$pwdSet = $false
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*WORDNEST_PASSWORD\s*=\s*(\S+)\s*$') { $pwdSet = $true }
    }
}

if (-not $pwdSet) {
    Write-Host ""
    Write-Host "⚠  你还没有设置访问密码（.env 里的 WORDNEST_PASSWORD）。" -ForegroundColor Yellow
    Write-Host "   隧道一旦开启，任何拿到这个网址的人都能打开你的词库、删除数据、消耗你的 AI 额度。" -ForegroundColor Yellow
    Write-Host "   建议先设置：在 .env 里加  WORDNEST_PASSWORD=你的密码   然后  docker compose up -d" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   仍要继续？5 秒后自动开始（Ctrl+C 取消）..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

Write-Host "==> 开启 Cloudflare 快速隧道（以下会出现一个 https://xxx.trycloudflare.com 地址）" -ForegroundColor Cyan
Write-Host "    手机用这个地址即可访问；Ctrl+C 停止。" -ForegroundColor DarkGray
Write-Host ""

& $exe tunnel --url http://127.0.0.1:5000 --no-autoupdate
