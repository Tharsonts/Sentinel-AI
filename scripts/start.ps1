$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$env:PYTHONPATH = Join-Path $projectRoot 'src'
$env:TEMP = Join-Path $projectRoot 'work'
$env:TMP = $env:TEMP
$env:YOLO_CONFIG_DIR = Join-Path $projectRoot 'cache/ultralytics'
$env:TORCH_HOME = Join-Path $projectRoot 'cache/torch'
$env:YOLO_AUTOINSTALL = 'false'
& (Join-Path $projectRoot '.venv/Scripts/python.exe') -m sentinel
