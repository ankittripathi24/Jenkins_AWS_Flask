# Docker & Kubernetes Deployment - Quick Start Guide

## 🚀 5-Minute Quick Start

### 1. Test Locally with Docker Compose (Linux/Mac/Windows)

```bash
# Build and start the application
docker-compose up -d

# Check if it's running
curl http://localhost:8080/api/health

# View logs
docker-compose logs -f

# Stop when done
docker-compose down
```

### 2. Build Docker Image

```bash
docker build -t flask-insights-hub:latest .
```

### 3. Push to Your Registry

#### **Windows (PowerShell):**
```powershell
# For Docker Hub
.\build-and-push.ps1 -RegistryType docker

# For AWS ECR
.\build-and-push.ps1 -RegistryType ecr

# For Azure ACR
.\build-and-push.ps1 -RegistryType acr -AcrName your-acr-name
```

#### **Linux/Mac (Bash):**
```bash
# For Docker Hub
bash build-and-push.sh -t docker

# For AWS ECR
bash build-and-push.sh -t ecr

# For Azure ACR
bash build-and-push.sh -t acr
```

### 4. Update Image Reference

Edit `k8s/02-deployment.yaml` line ~34:

```yaml
image: your-registry/flask-insights-hub:latest
```

Examples:
- Docker Hub: `username/flask-insights-hub:latest`
- AWS ECR: `123456789.dkr.ecr.us-east-1.amazonaws.com/flask-insights-hub:latest`
- Azure ACR: `myregistry.azurecr.io/flask-insights-hub:latest`

### 5. Deploy to Kubernetes

```bash
# Deploy all manifests
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -n flask-app -w

# Get service endpoint
kubectl get svc -n flask-app

# Test application
kubectl port-forward -n flask-app svc/flask-insights-hub 8080:80
curl http://localhost:8080/api/health
```

---

## 📋 File Structure

```
.
├── Dockerfile                 # Multi-stage production build
├── .dockerignore             # Optimize build context
├── docker-compose.yml        # Local testing
├── build-and-push.sh         # Linux/Mac deployment script
├── build-and-push.ps1        # Windows deployment script
├── Makefile                  # Quick commands (make build, make deploy)
│
├── k8s/                       # Kubernetes manifests
│   ├── 01-namespace.yaml      # Isolated namespace
│   ├── 02-deployment.yaml     # App deployment (3 replicas)
│   ├── 03-service.yaml        # LoadBalancer service
│   ├── 04-hpa.yaml           # Auto-scaling (3-10 pods)
│   ├── 05-rbac.yaml          # Security & permissions
│   ├── 06-network-policy.yaml # Firewall rules
│   ├── 07-pdb.yaml           # High availability
│   └── 08-configmap.yaml     # Configuration
│
├── DOCKER_DEPLOYMENT.md      # Full documentation
└── QUICKSTART.md             # This file
```

---

## 🔧 Using Makefile (Linux/Mac/Windows with make)

```bash
# View all commands
make help

# Build image
make build

# Test locally
make run
make test
make logs

# Stop local app
make stop

# Scan for vulnerabilities
make scan

# Deploy to Kubernetes
make deploy
make status
make logs-k8s

# Cleanup
make clean
make clean-k8s
```

---

## ☁️ Deploy to AWS EKS

### Prerequisites
```bash
# Install tools
# Windows: choco install awscli eksctl kubectl
# Mac: brew install awscli eksctl kubectl
# Linux: Use your package manager or download binaries
```

### Create Cluster (one-time)
```bash
eksctl create cluster \
  --name flask-app \
  --region us-east-1 \
  --node-type t3.medium \
  --nodes 3
```

### Deploy App
```bash
# Update credentials
aws eks update-kubeconfig --name flask-app --region us-east-1

# Push to ECR (use script above)

# Deploy
kubectl apply -f k8s/

# Get endpoint
kubectl get svc flask-insights-hub -n flask-app
```

---

## ☁️ Deploy to Azure AKS

### Prerequisites
```bash
# Install tools
# Windows: choco install azure-cli kubernetes-cli
# Mac: brew install azure-cli kubernetes-cli
# Linux: Use your package manager
```

### Create Cluster (one-time)
```bash
az group create --name flask-app-rg --location eastus

az aks create \
  --resource-group flask-app-rg \
  --name flask-app \
  --node-count 3
```

### Deploy App
```bash
# Update credentials
az aks get-credentials --resource-group flask-app-rg --name flask-app

# Push to ACR (use script above)

# Deploy
kubectl apply -f k8s/

# Get endpoint
kubectl get svc flask-insights-hub -n flask-app
```

---

## 🔍 Troubleshooting

### Check What's Running
```bash
# All resources
kubectl get all -n flask-app

# Just pods
kubectl get pods -n flask-app -o wide

# Pod details
kubectl describe pod <pod-name> -n flask-app

# Logs
kubectl logs <pod-name> -n flask-app
```

### Common Issues

**Pod won't start:**
```bash
kubectl describe pod <pod-name> -n flask-app
kubectl logs <pod-name> -n flask-app
```

**Service not accessible:**
```bash
# Test with port-forward
kubectl port-forward -n flask-app svc/flask-insights-hub 8080:80
curl http://localhost:8080/api/health
```

**Image not found:**
- Verify image URL in `k8s/02-deployment.yaml`
- Ensure registry credentials are correct
- For private registries: create image pull secret

**High CPU/Memory:**
```bash
# Check resource usage
kubectl top nodes
kubectl top pods -n flask-app

# Check autoscaler
kubectl get hpa -n flask-app
```

---

## 📦 Environment Variables

Configure in `k8s/08-configmap.yaml`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | 8080 | Port the app listens on |
| `BASE_PATH` | "" | URL path prefix (e.g., `/app`) |
| `WORKERS` | 4 | Gunicorn worker processes |
| `FLASK_ENV` | production | Flask environment |

To update:
```bash
# Edit configmap
kubectl edit configmap flask-app-config -n flask-app

# Restart pods to apply
kubectl rollout restart deployment/flask-insights-hub -n flask-app
```

---

## 🔒 Security Features

✅ **Built-in:**
- Non-root user execution
- Resource limits
- Health checks
- RBAC with minimal permissions
- Network policies
- Pod Disruption Budget for HA

⚠️ **Recommended additions:**
- Ingress with TLS
- Pod Security Policies
- Regular vulnerability scanning
- Secret management (AWS Secrets Manager, Azure Key Vault)
- Monitoring & logging

---

## 📊 Monitoring & Logs

### Live Logs
```bash
kubectl logs -n flask-app -l app=flask-insights-hub -f
```

### Check Autoscaling
```bash
kubectl get hpa -n flask-app --watch
```

### Performance
```bash
kubectl top nodes
kubectl top pods -n flask-app
```

---

## 🧹 Cleanup

### Local
```bash
docker-compose down -v
docker rmi flask-insights-hub:latest
```

### Kubernetes
```bash
# Delete everything
kubectl delete namespace flask-app

# Or just the app
kubectl delete -f k8s/
```

---

## 📚 Full Documentation

For complete details, see: [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)

---

## 💡 Pro Tips

1. **Test locally first**: `docker-compose up` before pushing
2. **Use tags**: `v1.0`, `v1.1` instead of just `latest`
3. **Monitor logs**: `kubectl logs -f` while deploying
4. **Scale on demand**: HPA scales 3-10 pods based on load
5. **Multiple environments**: Create separate namespaces for dev/staging/prod

---

## ✨ What's Included

✅ Production-ready Dockerfile (multi-stage, optimized)
✅ Docker Compose for local testing
✅ 8 Kubernetes manifests for enterprise deployment
✅ Auto-scaling (HPA) with 3-10 pods
✅ High availability (Pod Disruption Budget)
✅ Network policies and RBAC security
✅ Health checks and resource management
✅ Support for AWS EKS, Azure AKS, private clusters
✅ Automated build/push scripts for all platforms
✅ Comprehensive documentation

---

**Next Step**: Start with `docker-compose up` to test locally!
