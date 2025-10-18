<#
Build, scan for secrets, and push OctoBot Docker images to Docker Hub.

Usage examples (PowerShell):

  # Single-arch build, scan, push
  .\scripts\publish_docker.ps1 -Repo yourname/octobot -Tag 2.0.12-local

  # Multi-arch buildx build and push (linux/amd64 + linux/arm64) and also tag latest
  .\scripts\publish_docker.ps1 -Repo yourname/octobot -Tag 2.0.12 -UseBuildx -Platforms "linux/amd64,linux/arm64" -AlsoTagLatest

  # Dry run (no push), skip secret scan
  .\scripts\publish_docker.ps1 -Repo yourname/octobot -Tag test -NoPush -SkipSecretScan

Requires:
  - Docker CLI (and buildx for multi-arch)
  - Prior `docker login` to Docker Hub for push
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Repo,           # e.g., yourname/octobot
  [Parameter(Mandatory=$true)][string]$Tag,            # e.g., 2.0.12-local
  [string]$Context = ".",
  [string]$Dockerfile = "Dockerfile",
  [switch]$AlsoTagLatest,
  [switch]$UseBuildx,
  [string]$Platforms = "linux/amd64,linux/arm64",
  [switch]$SkipSecretScan,
  [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Fail([string]$msg) {
  Write-Error $msg
  exit 1
}

function Run([string]$cmd, [switch]$IgnoreErrors) {
  Write-Host "→ $cmd" -ForegroundColor Cyan
  & powershell -NoProfile -Command $cmd
  if(-not $IgnoreErrors -and $LASTEXITCODE -ne 0){ Fail("Command failed: $cmd") }
}

function RunLocal([string[]]$args, [switch]$IgnoreErrors) {
  $display = ($args -join ' ')
  Write-Host "→ $display" -ForegroundColor Cyan
  & @args
  if(-not $IgnoreErrors -and $LASTEXITCODE -ne 0){ Fail("Command failed: $display") }
}

$image = "$Repo:$Tag"
Write-Host ("Building image: {0}" -f $image) -ForegroundColor Green

# 1) Secret scan (unless skipped)
if(-not $SkipSecretScan){
  $scanner = Join-Path (Resolve-Path ".").Path "scripts/scan_secrets.ps1"
  if(Test-Path $scanner){
    Write-Host "Running secret scan..." -ForegroundColor Yellow
    # Prefer pwsh when available
    if(Get-Command pwsh -ErrorAction SilentlyContinue){
      & pwsh -File $scanner
    } else {
      & powershell -NoProfile -ExecutionPolicy Bypass -File $scanner
    }
    if($LASTEXITCODE -ne 0){ Fail("Secret scan reported findings. Resolve or rerun with -SkipSecretScan.") }
  } else {
    Write-Host "Secret scanner not found at scripts/scan_secrets.ps1. Skipping." -ForegroundColor Yellow
  }
} else {
  Write-Host "Skipping secret scan as requested." -ForegroundColor Yellow
}

# 2) Build
if($UseBuildx){
  # Multi-arch build. Push during buildx when pushing is requested; otherwise --load for local testing (single arch).
  if($NoPush){
    RunLocal @('docker','buildx','build','--platform', $Platforms, '-f', $Dockerfile, '-t', $image, '--load', $Context)
    $pushedDuringBuild = $false
  } else {
    RunLocal @('docker','buildx','build','--platform', $Platforms, '-f', $Dockerfile, '-t', $image, '--push', $Context)
    $pushedDuringBuild = $true
  }
} else {
  RunLocal @('docker','build','-f', $Dockerfile, '-t', $image, $Context)
  $pushedDuringBuild = $false
}

# 3) Push (if not already pushed during buildx)
if(-not $NoPush -and -not $pushedDuringBuild){
  RunLocal @('docker','push', $image)
}

# 4) Also tag latest
if($AlsoTagLatest){
  $latest = "$Repo:latest"
  RunLocal @('docker','tag', $image, $latest)
  if(-not $NoPush){ RunLocal @('docker','push', $latest) }
}

Write-Host "Done." -ForegroundColor Green

