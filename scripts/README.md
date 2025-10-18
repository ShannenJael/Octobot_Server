# Conda helper scripts

`create_conda_env.ps1` - PowerShell helper to create a conda env, install
`tulipindicators` from conda-forge and install pip requirements.

Usage:

1. Install Miniconda or Miniforge and ensure `conda` is on PATH.
2. From project root run (PowerShell):

```powershell
.\scripts\create_conda_env.ps1 -EnvName octobot
```

This script will create (or reuse) a conda env named `octobot`, install
`tulipindicators` (or `tulipy`) from conda-forge and then pip-install the
project's `requirements.txt` inside that environment.


Secret scanning
- `scan_secrets.ps1` — quick scanner for obvious secrets in the repo.

Usage:

```powershell
pwsh -File .\scripts\scan_secrets.ps1
```

Notes:
- It excludes `user/config.sample.json` but will flag any real secrets in `user/config.json` or elsewhere.
- Exits with code 1 when findings are detected.


Docker publish helper
- `publish_docker.ps1` — builds, secret‑scans, tags, and pushes images to Docker Hub.

Usage examples:

```powershell
# Single-arch build, scan, push
.\u005cscripts\u005cpublish_docker.ps1 -Repo yourname/octobot -Tag 2.0.12-local

# Multi-arch buildx build and push
.\u005cscriptspublish_docker.ps1 -Repo yourname/octobot -Tag 2.0.12 -UseBuildx -Platforms "linux/amd64,linux/arm64" -AlsoTagLatest

# Dry run (no push), skip secret scan
.scripts\u005cpublish_docker.ps1 -Repo yourname/octobot -Tag test -NoPush -SkipSecretScan
```

Prereqs:
- Run `docker login` before pushing.
- For multi-arch, ensure Docker Buildx is available and configured.
