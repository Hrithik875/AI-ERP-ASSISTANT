# ================================================================
# AI ERP Assistant — Lambda Deployment Script (PowerShell)
# ================================================================
# Packages the entire modular FastAPI backend into a zip and deploys
# to AWS Lambda.
#
# Stack: Bedrock + Aurora MySQL + Qdrant + S3 + Polly + Transcribe
#
# Usage: .\deploy.ps1
# Output: lambda_package.zip (uploaded to Lambda automatically)
# ================================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " AI ERP Assistant - Lambda Packager" -ForegroundColor Cyan
Write-Host " (Bedrock + Aurora MySQL + Qdrant)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Clean previous builds ────────────────────────────────────────
Write-Host "[1/6] Cleaning previous build..." -ForegroundColor Yellow
if (Test-Path "package") { Remove-Item -Recurse -Force "package" }
if (Test-Path "lambda_package.zip") { Remove-Item -Force "lambda_package.zip" }
Write-Host "  Done." -ForegroundColor Green

# ── Step 2: Create package directory ─────────────────────────────────────
Write-Host "[2/6] Creating package directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "package" -Force | Out-Null
Write-Host "  Done." -ForegroundColor Green

# ── Step 3: Install dependencies into package directory ──────────────────
Write-Host "[3/6] Installing dependencies..." -ForegroundColor Yellow

$dockerRunning = $false
try {
    $dockerInfo = docker info 2>$null
    if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
} catch { }

if ($dockerRunning) {
    Write-Host "  Using Docker to install packages natively for Linux..." -ForegroundColor Gray
    docker run --rm -v "$PWD`:/var/task" python:3.10 bash -c "pip install -r /var/task/requirements.txt -t /var/task/package --quiet"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Fatal: Docker pip install failed." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  Docker not running. Falling back to native pip with manylinux platform..." -ForegroundColor Yellow
    pip install -r requirements.txt -t package --platform manylinux2014_x86_64 --implementation cp --python-version 3.10 --only-binary=:all: --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Fatal: Native pip install failed. Please start Docker Desktop to build dependencies." -ForegroundColor Red
        exit 1
    }
}

Write-Host "  Done." -ForegroundColor Green

# ── Step 4: Copy application code (all modules) ─────────────────────────
Write-Host "[4/6] Copying application code..." -ForegroundColor Yellow

# Copy root-level Python modules
Copy-Item "main.py" -Destination "package/main.py" -Force
Copy-Item "config.py" -Destination "package/config.py" -Force

# Copy packages (db, ai, services, routes)
$packages = @("db", "ai", "services", "routes")
foreach ($pkg in $packages) {
    if (Test-Path $pkg) {
        $dest = "package/$pkg"
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        Copy-Item "$pkg/*.py" -Destination $dest -Recurse -Force
        Write-Host "  Copied $pkg/" -ForegroundColor Gray
    }
}

Write-Host "  Done." -ForegroundColor Green

# ── Step 5: Create ZIP package ───────────────────────────────────────────
Write-Host "[5/6] Creating lambda_package.zip..." -ForegroundColor Yellow
Set-Location "package"
Compress-Archive -Path * -DestinationPath "..\lambda_package.zip" -Force
Set-Location ..
Write-Host "  Done." -ForegroundColor Green

# ── Step 6: Automated AWS Deploy ─────────────────────────────────────────
Write-Host "[6/6] Pushing to AWS (S3 -> Lambda)..." -ForegroundColor Yellow

$awsCmd = "aws"
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    if (Test-Path "$env:ProgramFiles\Amazon\AWSCLIV2\aws.exe") {
        $awsCmd = "$env:ProgramFiles\Amazon\AWSCLIV2\aws.exe"
    }
}

if ((Get-Command aws -ErrorAction SilentlyContinue) -or ($awsCmd -ne "aws")) {
    Write-Host "  -> Uploading ZIP to S3 Bucket..." -ForegroundColor Gray
    & $awsCmd s3 cp "lambda_package.zip" "s3://bmsce-ai-erp-voice-bucket/lambda_package.zip" --region ap-southeast-2

    Write-Host "  -> Updating Lambda Function..." -ForegroundColor Gray
    & $awsCmd lambda update-function-code `
        --function-name erp-assistant-backend `
        --s3-bucket bmsce-ai-erp-voice-bucket `
        --s3-key lambda_package.zip `
        --region ap-southeast-2 | Out-Null

    Write-Host "  AWS DEPLOYMENT COMPLETE! Lambda is now running your latest code." -ForegroundColor Green
} else {
    Write-Host "  AWS CLI not found on this computer. Skipping auto-upload." -ForegroundColor Red
    Write-Host "  Please upload lambda_package.zip via browser manually." -ForegroundColor Gray
}

# ── Summary ──────────────────────────────────────────────────────────────
$zipSize = (Get-Item "lambda_package.zip").Length / 1MB
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  File: lambda_package.zip" -ForegroundColor White
Write-Host "  Size: $([math]::Round($zipSize, 2)) MB" -ForegroundColor White
Write-Host ""
Write-Host "  Stack:" -ForegroundColor White
Write-Host "    AI:      Amazon Bedrock (Claude 3 Sonnet)" -ForegroundColor Gray
Write-Host "    Embed:   Amazon Bedrock (Titan Embeddings V2)" -ForegroundColor Gray
Write-Host "    Database:Aurora MySQL" -ForegroundColor Gray
Write-Host "    Vector:  Qdrant" -ForegroundColor Gray
Write-Host "    Speech:  Amazon Transcribe + Polly" -ForegroundColor Gray
Write-Host "    Storage: Amazon S3" -ForegroundColor Gray
Write-Host ""
Write-Host "  Modules included:" -ForegroundColor White
Write-Host "    main.py, config.py" -ForegroundColor Gray
Write-Host "    db/ (connection, models, seed)" -ForegroundColor Gray
Write-Host "    ai/ (llm_service, embeddings, rag_pipeline, agent)" -ForegroundColor Gray
Write-Host "    services/ (s3, transcribe, polly)" -ForegroundColor Gray
Write-Host "    routes/ (health, voice, chat, analytics, documents, students)" -ForegroundColor Gray
Write-Host ""
