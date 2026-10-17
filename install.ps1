﻿# Cài Video Studio (skill + lệnh /video:*) cho Claude Code trên Windows.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host '1/5 Thư viện Python chính'
python -m pip install --disable-pip-version-check -q -r (Join-Path $repo 'requirements.txt')

Write-Host '2/5 VieNeu-TTS trong venv riêng'
$venv = Join-Path $env:USERPROFILE 'tools\venv_vieneu'
if (-not (Test-Path $venv)) { python -m venv $venv }
& (Join-Path $venv 'Scripts\python.exe') -m pip install --disable-pip-version-check -q vieneu

function Link($path, $target) {
    New-Item -ItemType Directory -Force (Split-Path $path) | Out-Null
    if (Test-Path $path) { Write-Host "Đã có $path - giữ nguyên." }
    else { New-Item -ItemType Junction -Path $path -Target $target | Out-Null; Write-Host "Liên kết $path -> $target" }
}
Write-Host '3/5 Skill video-studio'
Link (Join-Path $env:USERPROFILE '.claude\skills\video-studio') $repo
Write-Host '4/5 Lệnh /video:*'
Link (Join-Path $env:USERPROFILE '.claude\commands\video') (Join-Path $repo 'commands')

Write-Host '5/5 RIFE (nội suy khung, MIT) + YuNet (nhận diện mặt, opencv_zoo)'
$tools = Join-Path $env:USERPROFILE 'tools'
$rife = Join-Path $tools 'rife'
if (-not (Get-ChildItem $rife -Recurse -Filter 'rife-ncnn-vulkan.exe' -ErrorAction SilentlyContinue)) {
    New-Item -ItemType Directory -Force $rife | Out-Null
    $zip = Join-Path $rife 'rife.zip'
    Invoke-WebRequest 'https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-windows.zip' -OutFile $zip
    Expand-Archive $zip -DestinationPath $rife -Force
}
$models = Join-Path $tools 'models'; New-Item -ItemType Directory -Force $models | Out-Null
$yunet = Join-Path $models 'face_detection_yunet_2023mar.onnx'
if (-not (Test-Path $yunet)) {
    Invoke-WebRequest 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx' -OutFile $yunet
}

ffmpeg -hide_banner -filters 2>$null | Select-String -Pattern ' (ass|rubberband|loudnorm|sidechaincompress) ' | ForEach-Object { $_.Line }
Write-Host 'Playwright (đồ hoạ động bằng HTML)'
python -m pip install --disable-pip-version-check -q playwright
python -m playwright install chromium

Write-Host 'MCP server video-studio'
$srv = (Join-Path $repo 'scripts\mcp_server.py') -replace '\\', '/'
claude mcp add --scope user video-studio -e PYTHONIOENCODING=utf-8 -- python $srv

Write-Host 'Xong. Mở Claude Code, gõ /video: để xem các lệnh; công cụ MCP: mcp__video-studio__*.'
