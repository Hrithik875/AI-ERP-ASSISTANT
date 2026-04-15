# ================================================================
# AI ERP Assistant — Lambda Deployment Script (PowerShell)
# ================================================================
# This script packages the FastAPI backend into a zip file
# ready for upload to AWS Lambda.
#
# Usage: .\deploy.ps1
# Output: lambda_package.zip (upload this to Lambda)
# ================================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " AI ERP Assistant - Lambda Packager" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Clean previous builds ────────────────────────────────────────
Write-Host "[1/5] Cleaning previous build..." -ForegroundColor Yellow
if (Test-Path "package") { Remove-Item -Recurse -Force "package" }
if (Test-Path "lambda_package.zip") { Remove-Item -Force "lambda_package.zip" }
Write-Host "  Done." -ForegroundColor Green

# ── Step 2: Create package directory ─────────────────────────────────────
Write-Host "[2/5] Creating package directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "package" -Force | Out-Null
Write-Host "  Done." -ForegroundColor Green

# ── Step 3: Install dependencies into package directory ──────────────────
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
Write-Host "  This may take a minute..." -ForegroundColor Gray

# Install all dependencies into the package directory
# --platform manylinux2014_x86_64 ensures Linux-compatible packages for Lambda
# --only-binary :all: ensures we get pre-compiled wheels
pip install `
    --target ./package `
    --platform manylinux2014_x86_64 `
    --implementation cp `
    --python-version 3.10 `
    --only-binary :all: `
    -r requirements.txt `
    --quiet

# Note: boto3 is pre-installed on Lambda, but we include it for
# local testing compatibility. Lambda will use its own version.
Write-Host "  Done." -ForegroundColor Green

# ── Step 4: Copy application code ────────────────────────────────────────
Write-Host "[4/5] Copying application code..." -ForegroundColor Yellow
Copy-Item "main.py" -Destination "package/main.py" -Force
Write-Host "  Done." -ForegroundColor Green

# ── Step 5: Create ZIP package ───────────────────────────────────────────
Write-Host "[5/5] Creating lambda_package.zip..." -ForegroundColor Yellow
Set-Location "package"
Compress-Archive -Path * -DestinationPath "..\lambda_package.zip" -Force
Set-Location ..
Write-Host "  Done." -ForegroundColor Green

# ── Step 6: Automated AWS Deploy ─────────────────────────────────────────
Write-Host "[6/6] Pushing to AWS (S3 -> Lambda)..." -ForegroundColor Yellow
if (Get-Command aws -ErrorAction SilentlyContinue) {
    Write-Host "  -> Uploading ZIP to S3 Bucket..." -ForegroundColor Gray
    aws s3 cp "lambda_package.zip" "s3://bmsce-ai-erp-voice-bucket/lambda_package.zip" --region ap-southeast-2

    Write-Host "  -> Updating Lambda Function..." -ForegroundColor Gray
    aws lambda update-function-code `
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
Write-Host " Packaging Phase Finished!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  File: lambda_package.zip" -ForegroundColor White
Write-Host "  Size: $([math]::Round($zipSize, 2)) MB" -ForegroundColor White
Write-Host ""
