# Flask Application Dockerization Guide

## Overview
Your Flask application has been dockerized and is ready for deployment on AWS, Azure, or any private Kubernetes cluster. This guide provides step-by-step instructions for building, testing, and deploying your application.

## Project Structure
```
.
├── Dockerfile                 # Production-ready multi-stage Dockerfile
├── .dockerignore             # Optimization for Docker builds
├── docker-compose.yml        # Local testing with Docker Compose
├── DOCKER_DEPLOYMENT.md      # This file
└── k8s/                       # Kubernetes manifests
    ├── 01-namespace.yaml      # Namespace
    ├── 02-deployment.yaml     # Deployment with resource limits
    ├── 03-service.yaml        # LoadBalancer service
    ├── 04-hpa.yaml           # Horizontal Pod Autoscaler
    ├── 05-rbac.yaml          # Service account and RBAC
    ├── 06-network-policy.yaml # Network security
    ├── 07-pdb.yaml           # Pod Disruption Budget
    └── 08-configmap.yaml     # Configuration
```

## Local Testing with Docker Compose

### Prerequisites
- Docker Desktop installed and running
- Docker Compose installed

### Build and Run Locally
```bash
# Build the image
docker-compose build

# Start the application
docker-compose up -d

# Check logs
docker-compose logs -f flask-app

# Test the application
curl http://localhost:8080/api/health
curl http://localhost:8080/

# Stop the application
docker-compose down
```

## Building Docker Images

### Option 1: Local Build
```bash
# Build the image
docker build -t flask-insights-hub:latest .

# Test the image locally
docker run -p 8080:8080 flask-insights-hub:latest

# Verify it's running
curl http://localhost:8080/api/health
```

### Option 2: Build for Specific Registry

#### AWS ECR (Elastic Container Registry)
```bash
# Set variables
AWS_ACCOUNT_ID=your-account-id
AWS_REGION=us-east-1
ECR_REPO_NAME=flask-insights-hub

# Create repository (one-time)
aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and tag
docker build -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest .

# Push to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest
```

#### Azure Container Registry (ACR)
```bash
# Set variables
ACR_NAME=your-acr-name
ACR_REPO_NAME=flask-insights-hub

# Create registry (one-time, if needed)
az acr create --resource-group your-rg --name $ACR_NAME --sku Basic

# Login to ACR
az acr login --name $ACR_NAME

# Build and tag
docker build -t $ACR_NAME.azurecr.io/$ACR_REPO_NAME:latest .

# Push to ACR
docker push $ACR_NAME.azurecr.io/$ACR_REPO_NAME:latest
```

#### Docker Hub
```bash
# Login
docker login

# Build and tag
docker build -t your-username/flask-insights-hub:latest .

# Push
docker push your-username/flask-insights-hub:latest
```

## Scanning for Vulnerabilities

### Using Trivy (recommended)
```bash
# Install Trivy if not already installed
# For Windows: https://github.com/aquasecurity/trivy/releases

# Scan the image
trivy image flask-insights-hub:latest

# Generate detailed report
trivy image --format json flask-insights-hub:latest > vulnerability-report.json
```

### Using Docker Scout (for Docker images)
```bash
docker scout cves flask-insights-hub:latest
```

## Kubernetes Deployment

### Prerequisites
- `kubectl` installed and configured
- Access to a Kubernetes cluster (EKS, AKS, or private)
- Docker image pushed to a registry accessible from your cluster

### Update Image Reference
Before deploying, update the image reference in `k8s/02-deployment.yaml`:

```yaml
# Line ~34 in deployment.yaml
image: your-registry/flask-insights-hub:latest
```

### Deploy to Kubernetes

#### All-in-One Deployment
```bash
# Deploy all manifests
kubectl apply -f k8s/

# Verify deployment
kubectl get all -n flask-app
kubectl get pods -n flask-app -w

# Get service endpoint
kubectl get svc -n flask-app

# Test the application
kubectl port-forward -n flask-app svc/flask-insights-hub 8080:80
curl http://localhost:8080/api/health
```

#### Individual Component Deployment (if needed)
```bash
# Deploy namespace first
kubectl apply -f k8s/01-namespace.yaml

# Deploy other components
kubectl apply -f k8s/02-deployment.yaml
kubectl apply -f k8s/03-service.yaml
kubectl apply -f k8s/04-hpa.yaml
kubectl apply -f k8s/05-rbac.yaml
kubectl apply -f k8s/06-network-policy.yaml
kubectl apply -f k8s/07-pdb.yaml
kubectl apply -f k8s/08-configmap.yaml
```

### Monitor Deployment

```bash
# Watch deployment rollout
kubectl rollout status deployment/flask-insights-hub -n flask-app

# Check pod status
kubectl get pods -n flask-app -o wide

# View pod logs
kubectl logs -n flask-app -l app=flask-insights-hub -f

# Describe deployment
kubectl describe deployment flask-insights-hub -n flask-app

# Check horizontal pod autoscaler
kubectl get hpa -n flask-app
```

## AWS EKS Specific Instructions

### Create EKS Cluster (if needed)
```bash
# Prerequisites: eksctl installed

eksctl create cluster \
  --name flask-app-cluster \
  --region us-east-1 \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 3 \
  --nodes-max 10

# Update kubeconfig
aws eks update-kubeconfig --name flask-app-cluster --region us-east-1
```

### Deploy to EKS
```bash
# Configure kubectl for EKS
aws eks update-kubeconfig --region us-east-1 --name flask-app-cluster

# Deploy application
kubectl apply -f k8s/

# Get LoadBalancer endpoint
kubectl get svc flask-insights-hub -n flask-app
```

### Set up ECR Pull Secret (if image is private)
```bash
# Create secret for ECR authentication
kubectl create secret docker-registry ecr-secret \
  --docker-server=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com \
  --docker-username=AWS \
  --docker-password=$(aws ecr get-login-password --region $AWS_REGION) \
  -n flask-app

# Update deployment to use the secret
# Add imagePullSecrets to deployment spec:
# imagePullSecrets:
# - name: ecr-secret
```

## Azure AKS Specific Instructions

### Create AKS Cluster (if needed)
```bash
# Prerequisites: Azure CLI installed

az group create --name flask-app-rg --location eastus

az aks create \
  --resource-group flask-app-rg \
  --name flask-app-cluster \
  --node-count 3 \
  --vm-set-type VirtualMachineScaleSets \
  --load-balancer-sku standard

# Get credentials
az aks get-credentials --resource-group flask-app-rg --name flask-app-cluster
```

### Deploy to AKS
```bash
# Configure kubectl for AKS
az aks get-credentials --resource-group flask-app-rg --name flask-app-cluster

# Deploy application
kubectl apply -f k8s/

# Get LoadBalancer endpoint
kubectl get svc flask-insights-hub -n flask-app
```

### Configure ACR Integration (recommended)
```bash
# Attach ACR to AKS
az aks update \
  --name flask-app-cluster \
  --resource-group flask-app-rg \
  --attach-acr $ACR_NAME

# AKS now has pull access to your ACR
```

## Environment Variables Configuration

Your application supports the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Port the Flask app listens on |
| `BASE_PATH` | "" | Base path for deployment (e.g., `/insights-hub`) |
| `WORKERS` | 4 | Number of Gunicorn worker processes |
| `FLASK_ENV` | production | Flask environment (development/production) |

### Update Configuration

Edit `k8s/08-configmap.yaml` to change environment variables:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: flask-app-config
  namespace: flask-app
data:
  PORT: "8080"
  BASE_PATH: "/my-app"  # Change this
  WORKERS: "4"
  FLASK_ENV: "production"
```

Apply the update:
```bash
kubectl apply -f k8s/08-configmap.yaml
kubectl rollout restart deployment/flask-insights-hub -n flask-app
```

## Security Best Practices

✅ **Implemented in Dockerfile:**
- Non-root user execution (UID 1000)
- Multi-stage build (smaller image size)
- No unnecessary packages installed
- Python unbuffered output for logging

✅ **Implemented in Kubernetes Manifests:**
- Pod Security Context (non-root, read-only filesystem where possible)
- Security contexts with capability dropping
- Network policies for traffic control
- Resource limits and requests
- Pod Disruption Budget for high availability
- RBAC with minimal permissions
- Health checks (liveness and readiness probes)

⚠️ **Additional Hardening (Optional):**
- Implement Ingress with TLS termination
- Use Pod Security Policies or Pod Security Standards
- Implement Network Policies more restrictively
- Use service mesh (Istio, Linkerd) for advanced traffic management
- Enable audit logging
- Scan images regularly for CVEs

## Troubleshooting

### Pod won't start
```bash
# Check pod status
kubectl describe pod <pod-name> -n flask-app

# View pod logs
kubectl logs <pod-name> -n flask-app

# Check events
kubectl get events -n flask-app --sort-by='.lastTimestamp'
```

### Service not accessible
```bash
# Verify service
kubectl get svc -n flask-app

# Port-forward for testing
kubectl port-forward -n flask-app svc/flask-insights-hub 8080:80

# Check endpoints
kubectl get endpoints -n flask-app
```

### Image pull errors
```bash
# Verify image exists in registry
# For AWS ECR:
aws ecr describe-images --repository-name flask-insights-hub

# For Azure ACR:
az acr repository show --name $ACR_NAME --repository flask-insights-hub

# Check image pull secret
kubectl get secrets -n flask-app
kubectl describe secret <secret-name> -n flask-app
```

### Performance issues
```bash
# Check resource usage
kubectl top nodes
kubectl top pods -n flask-app

# Check HPA status
kubectl get hpa -n flask-app
kubectl describe hpa flask-insights-hub-hpa -n flask-app

# Check HPA metrics
kubectl get hpa flask-insights-hub-hpa -n flask-app --watch
```

## Cleanup

### Local Docker Cleanup
```bash
# Stop and remove containers
docker-compose down

# Remove image
docker rmi flask-insights-hub:latest
```

### Kubernetes Cleanup
```bash
# Delete all resources in namespace
kubectl delete namespace flask-app

# Or delete individual resources
kubectl delete -f k8s/
```

## Next Steps

1. **Update Image Registry**: Update the image reference in `k8s/02-deployment.yaml` with your actual registry
2. **Configure CI/CD**: Set up GitHub Actions, GitLab CI, or Jenkins to automate builds and deployments
3. **Add Monitoring**: Integrate Prometheus, Grafana, or cloud-native monitoring solutions
4. **Set up Logging**: Configure ELK stack or cloud provider's logging service
5. **Enable Ingress**: Set up Ingress controller for domain-based routing and TLS
6. **Implement Secrets Management**: Use AWS Secrets Manager, Azure Key Vault, or Kubernetes Secrets for sensitive data

## Support and Documentation

- Flask: https://flask.palletsprojects.com/
- Gunicorn: https://gunicorn.org/
- Docker: https://docs.docker.com/
- Kubernetes: https://kubernetes.io/docs/
- AWS EKS: https://docs.aws.amazon.com/eks/
- Azure AKS: https://docs.microsoft.com/en-us/azure/aks/

---

**Created**: Docker deployment for Flask Insights Hub application
**Compatibility**: AWS EKS, Azure AKS, Private Kubernetes Clusters, Docker Compose
