#!/bin/bash

# Quick deployment script for Flask application
# This script builds and pushes your Docker image to a registry

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
REGISTRY_TYPE="docker"  # docker, ecr, acr
IMAGE_NAME="flask-insights-hub"
IMAGE_TAG="latest"

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Print usage
usage() {
    echo "Usage: $0 -t <registry_type> [-i <image_name>] [-g <tag>]"
    echo ""
    echo "Options:"
    echo "  -t  Registry type: docker, ecr, or acr (required)"
    echo "  -i  Image name (default: flask-insights-hub)"
    echo "  -g  Image tag (default: latest)"
    echo ""
    echo "Examples:"
    echo "  $0 -t docker -i myapp -g v1.0"
    echo "  $0 -t ecr"
    echo "  $0 -t acr"
}

# Parse arguments
while getopts "t:i:g:h" opt; do
    case $opt in
        t) REGISTRY_TYPE="$OPTARG" ;;
        i) IMAGE_NAME="$OPTARG" ;;
        g) IMAGE_TAG="$OPTARG" ;;
        h) usage; exit 0 ;;
        *) usage; exit 1 ;;
    esac
done

# Check Docker is installed
if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

print_info "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
print_success "Image built successfully"

# Build and push based on registry type
case $REGISTRY_TYPE in
    docker)
        print_info "Pushing to Docker Hub"
        print_info "Make sure you're logged in: docker login"
        
        if ! docker push ${IMAGE_NAME}:${IMAGE_TAG}; then
            print_error "Failed to push to Docker Hub"
            exit 1
        fi
        print_success "Pushed to Docker Hub: ${IMAGE_NAME}:${IMAGE_TAG}"
        ;;
    
    ecr)
        print_info "Setting up AWS ECR"
        
        if ! command_exists aws; then
            print_error "AWS CLI is not installed. Please install it first."
            exit 1
        fi
        
        # Get AWS account ID and region
        AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        AWS_REGION=${AWS_REGION:-us-east-1}
        ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE_NAME}"
        
        print_info "AWS Account: $AWS_ACCOUNT_ID"
        print_info "AWS Region: $AWS_REGION"
        
        # Login to ECR
        print_info "Logging in to ECR..."
        aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
        print_success "Logged in to ECR"
        
        # Create repository if it doesn't exist
        if ! aws ecr describe-repositories --repository-names ${IMAGE_NAME} --region ${AWS_REGION} >/dev/null 2>&1; then
            print_info "Creating ECR repository..."
            aws ecr create-repository --repository-name ${IMAGE_NAME} --region ${AWS_REGION}
            print_success "ECR repository created"
        fi
        
        # Tag and push
        docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REPO}:${IMAGE_TAG}
        print_info "Pushing to ECR: ${ECR_REPO}:${IMAGE_TAG}"
        docker push ${ECR_REPO}:${IMAGE_TAG}
        print_success "Pushed to ECR successfully"
        
        print_info "Image URI: ${ECR_REPO}:${IMAGE_TAG}"
        ;;
    
    acr)
        print_info "Setting up Azure Container Registry"
        
        if ! command_exists az; then
            print_error "Azure CLI is not installed. Please install it first."
            exit 1
        fi
        
        # Get ACR name from environment or prompt
        ACR_NAME=${ACR_NAME:-}
        if [ -z "$ACR_NAME" ]; then
            read -p "Enter your ACR name: " ACR_NAME
        fi
        
        print_info "ACR Name: $ACR_NAME"
        
        # Login to ACR
        print_info "Logging in to ACR..."
        az acr login --name ${ACR_NAME}
        print_success "Logged in to ACR"
        
        # Tag and push
        ACR_REPO="${ACR_NAME}.azurecr.io/${IMAGE_NAME}"
        docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ACR_REPO}:${IMAGE_TAG}
        print_info "Pushing to ACR: ${ACR_REPO}:${IMAGE_TAG}"
        docker push ${ACR_REPO}:${IMAGE_TAG}
        print_success "Pushed to ACR successfully"
        
        print_info "Image URI: ${ACR_REPO}:${IMAGE_TAG}"
        ;;
    
    *)
        print_error "Unknown registry type: $REGISTRY_TYPE"
        echo "Supported types: docker, ecr, acr"
        exit 1
        ;;
esac

print_success "Build and push completed successfully!"
echo ""
echo "Next steps:"
echo "1. Update the image reference in k8s/02-deployment.yaml"
echo "2. Deploy to Kubernetes: kubectl apply -f k8s/"
echo "3. Monitor deployment: kubectl get pods -n flask-app -w"
