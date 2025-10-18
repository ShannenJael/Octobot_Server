<#
Simple repository secret scanner (PowerShell).

Usage:
  pwsh -File .\scripts\scan_secrets.ps1

Exits with code 1 when potential secrets are found, 0 otherwise.
Customize $ExcludePaths to suppress known-safe files (e.g., sample configs).
#>

param(
  [string]$Root = "."
)

$ErrorActionPreference = "Stop"

$Patterns = @(
  'api[-_ ]?key\s*[:=]\s*"?[A-Za-z0-9_\-]{12,}',
  'api[-_ ]?secret\s*[:=]\s*"?[A-Za-z0-9_\-]{12,}',
  'client[-_ ]?secret\s*[:=]\s*"?[A-Za-z0-9_\-]{8,}',
  'token\s*[:=]\s*"?[A-Za-z0-9_\-\.]{12,}',
  'bearer\s+[A-Za-z0-9_\-\.]+',
  'pass(word|phrase)\s*[:=]\s*"?.+',
  'supabase\.auth\.token',
  'openai[-_ ]?(secret[-_ ]?key|api[-_ ]?key)\s*[:=]\s*"?.+',
  '-----BEGIN (?:RSA|EC|OPENSSH) PRIVATE KEY-----'
)

$ExcludePaths = @(
  "user/config.sample.json",
  ".git",
  ".venv",
  "env",
  "venv",
  "node_modules"
)

function Should-Exclude($path) {
  foreach ($ex in $ExcludePaths) {
    if ($path -like "*$ex*") { return $true }
  }
  return $false
}

$findings = @()
Get-ChildItem -Path $Root -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { -not (Should-Exclude $_.FullName) } |
  ForEach-Object {
    $file = $_.FullName
    try {
      $content = Get-Content -Raw -LiteralPath $file -ErrorAction Stop
    } catch {
      return
    }
    foreach ($pat in $Patterns) {
      $matches = Select-String -InputObject $content -Pattern $pat -AllMatches
      if ($matches) {
        $lines = Get-Content -LiteralPath $file
        foreach ($m in $matches.Matches) {
          $lineNumber = ($content.Substring(0, $m.Index) -split "`n").Count
          $snippet = $lines[$lineNumber - 1]
          $findings += [pscustomobject]@{
            File = $file
            Line = $lineNumber
            Pattern = $pat
            Snippet = $snippet
          }
        }
      }
    }
  }

if ($findings.Count -gt 0) {
  Write-Host "Potential secrets found:" -ForegroundColor Red
  $findings | Sort-Object File, Line | ForEach-Object {
    Write-Host ("{0}:{1} {2}" -f $_.File, $_.Line, $_.Snippet)
  }
  exit 1
} else {
  Write-Host "No obvious secrets detected." -ForegroundColor Green
  exit 0
}

