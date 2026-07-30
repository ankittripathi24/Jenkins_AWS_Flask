# build-and-push.ps1
# PowerShell script for building and pushing Docker images
# Compatible with Windows, also requires Docker Desktop

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("docker", "ecr", "acr")]
    [string]$RegistryType,
    
    [string]$ImageName = "flask-insights-hub",
    [string]$ImageTag = "latest",
    [string]$AcrName = ""
)

$ErrorActionPreference = "Stop"

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Yellow
}

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error-Custom "Docker is not installed. Please install Docker Desktop first."
    exit 1
}

Write-Info "Building Docker image: ${ImageName}:${ImageTag}"
docker build -t "${ImageName}:${ImageTag}" .
if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Failed to build image"
    exit 1
}
Write-Success "Image built successfully"

switch ($RegistryType) {
    "docker" {
        Write-Info "Pushing to Docker Hub"
        Write-Info "Make sure you're logged in: docker login"
        
        docker push "${ImageName}:${ImageTag}"
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to push to Docker Hub"
            exit 1
        }
        Write-Success "Pushed to Docker Hub: ${ImageName}:${ImageTag}"
    }
    
    "ecr" {
        Write-Info "Setting up AWS ECR"
        
        if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
            Write-Error-Custom "AWS CLI is not installed. Please install it first."
            exit 1
        }
        
        # Get AWS details
        $AwsAccountId = aws sts get-caller-identity --query Account --output text
        $AwsRegion = $env:AWS_REGION -or "us-east-1"
        $EcrRepo = "${AwsAccountId}.dkr.ecr.${AwsRegion}.amazonaws.com/${ImageName}"
        
        Write-Info "AWS Account: $AwsAccountId"
        Write-Info "AWS Region: $AwsRegion"
        
        # Login to ECR
        Write-Info "Logging in to ECR..."
        aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin "${AwsAccountId}.dkr.ecr.${AwsRegion}.amazonaws.com"
        Write-Success "Logged in to ECR"
        
        # Create repository if needed
        try {
            aws ecr describe-repositories --repository-names $ImageName --region $AwsRegion | Out-Null
        } catch {
            Write-Info "Creating ECR repository..."
            aws ecr create-repository --repository-name $ImageName --region $AwsRegion
            Write-Success "ECR repository created"
        }
        
        # Tag and push
        docker tag "${ImageName}:${ImageTag}" "${EcrRepo}:${ImageTag}"
        Write-Info "Pushing to ECR: ${EcrRepo}:${ImageTag}"
        docker push "${EcrRepo}:${ImageTag}"
        Write-Success "Pushed to ECR successfully"
        Write-Info "Image URI: ${EcrRepo}:${ImageTag}"
    }
    
    "acr" {
        Write-Info "Setting up Azure Container Registry"
        
        if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
            Write-Error-Custom "Azure CLI is not installed. Please install it first."
            exit 1
        }
        
        if ([string]::IsNullOrEmpty($AcrName)) {
            $AcrName = Read-Host "Enter your ACR name"
        }
        
        Write-Info "ACR Name: $AcrName"
        
        # Login to ACR
        Write-Info "Logging in to ACR..."
        az acr login --name $AcrName
        Write-Success "Logged in to ACR"
        
        # Tag and push
        $AcrRepo = "${AcrName}.azurecr.io/${ImageName}"
        docker tag "${ImageName}:${ImageTag}" "${AcrRepo}:${ImageTag}"
        Write-Info "Pushing to ACR: ${AcrRepo}:${ImageTag}"
        docker push "${AcrRepo}:${ImageTag}"
        Write-Success "Pushed to ACR successfully"
        Write-Info "Image URI: ${AcrRepo}:${ImageTag}"
    }
}

Write-Success "Build and push completed successfully!"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Update the image reference in k8s/02-deployment.yaml"
Write-Host "2. Deploy to Kubernetes: kubectl apply -f k8s/"
Write-Host "3. Monitor deployment: kubectl get pods -n flask-app -w"
