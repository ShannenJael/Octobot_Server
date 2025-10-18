<#
Create a conda environment for OctoBot and install prebuilt tulip indicators.

Usage (PowerShell):
  1) Install Miniconda or Miniforge if you don't have conda (see message below).
  2) From project root, run (PowerShell):
       .\scripts\create_conda_env.ps1 -EnvName octobot

This script will:
 - Check for conda on PATH
 - Create a conda env with Python 3.10
 - Add conda-forge channel and set strict priority
 - Install tulipindicators from conda-forge
 - Install pip requirements from requirements.txt inside the env

Note: If you prefer Miniforge (conda-forge native) install it instead of Miniconda.
#>
param(
    [string]$EnvName = "octobot",
    [string]$PythonVersion = "3.10"
)

function Fail([string]$msg){
    Write-Error $msg
    exit 1
}

# Check conda presence
try{
    $conda = & conda --version 2>$null
}catch{
    Write-Host "Conda not found on PATH. Please install Miniconda or Miniforge first." -ForegroundColor Yellow
    Write-Host "Miniconda: https://repo.anaconda.com/miniconda/" -ForegroundColor Cyan
    Write-Host "Miniforge (recommended for conda-forge): https://github.com/conda-forge/miniforge/releases/latest" -ForegroundColor Cyan
    Fail("Conda missing")
}

Write-Host "Conda detected: $conda" -ForegroundColor Green

# Create env
Write-Host "Creating conda env '$EnvName' with Python $PythonVersion..." -ForegroundColor Cyan
& conda create -n $EnvName python=$PythonVersion -y | Out-Null
if($LASTEXITCODE -ne 0){ Fail("Failed to create conda environment") }

# Activate env
Write-Host "Activating env..." -ForegroundColor Cyan
# Activation requires a new shell or 'conda activate' be available
& conda activate $EnvName
if($LASTEXITCODE -ne 0){
    Write-Host "Failed to activate env in this shell. Try opening a new shell and run: conda activate $EnvName" -ForegroundColor Yellow
    exit 0
}

# Add conda-forge and install tulipindicators
Write-Host "Configuring conda-forge channel and installing tulipindicators..." -ForegroundColor Cyan
& conda config --add channels conda-forge
& conda config --set channel_priority strict
& conda install -n $EnvName tulipindicators -y
if($LASTEXITCODE -ne 0){
    Write-Host "Failed to install 'tulipindicators' directly. Trying 'tulipy'..." -ForegroundColor Yellow
    & conda install -n $EnvName tulipy -y
    if($LASTEXITCODE -ne 0){ Fail("Failed to install tulip package from conda-forge. Try installing manually or use Miniforge.") }
}

# Install pip requirements
Write-Host "Installing pip requirements inside the conda env..." -ForegroundColor Cyan
& conda run -n $EnvName python -m pip install --upgrade pip setuptools wheel
& conda run -n $EnvName python -m pip install -r requirements.txt
if($LASTEXITCODE -ne 0){ Fail("pip install -r requirements.txt failed. Check output for missing packages.") }

Write-Host "Conda environment '$EnvName' ready. Activate it with: conda activate $EnvName" -ForegroundColor Green
# Build a safe, printable verify command string (escape inner quotes) and print it
$verifyCmd = "conda run -n $EnvName python -c `"import tulipy; print('tulipy OK', getattr(tulipy,'__version__','unknown'))`""
Write-Host "Verify tulip: $verifyCmd" -ForegroundColor Cyan
