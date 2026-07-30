# Quick start Makefile for Docker operations
# Usage: make build, make push, make deploy, etc.

.PHONY: help build run test push deploy clean

# Variables
IMAGE_NAME ?= flask-insights-hub
IMAGE_TAG ?= latest
REGISTRY ?= your-registry
NAMESPACE ?= flask-app
DOCKER_COMPOSE_FILE ?= docker-compose.yml
K8S_DIR ?= k8s

help:
	@echo "Flask Application Docker Operations"
	@echo "===================================="
	@echo "Available commands:"
	@echo "  make build              - Build Docker image locally"
	@echo "  make run                - Run application locally with docker-compose"
	@echo "  make stop               - Stop local application"
	@echo "  make logs               - View application logs"
	@echo "  make test               - Run health check"
	@echo "  make scan               - Scan image for vulnerabilities (requires trivy)"
	@echo "  make push               - Push image to registry"
	@echo "  make deploy             - Deploy to Kubernetes"
	@echo "  make status             - Check Kubernetes deployment status"
	@echo "  make logs-k8s           - View Kubernetes pod logs"
	@echo "  make clean              - Remove local Docker resources"
	@echo "  make clean-k8s          - Delete Kubernetes resources"

build:
	@echo "Building Docker image: $(IMAGE_NAME):$(IMAGE_TAG)"
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

run:
	@echo "Starting application with Docker Compose..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) up -d
	@echo "Application started. Check logs with: make logs"

stop:
	@echo "Stopping application..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) down

logs:
	docker-compose -f $(DOCKER_COMPOSE_FILE) logs -f

test:
	@echo "Testing application..."
	@sleep 2
	@curl -f http://localhost:8080/api/health && echo "\n✓ Health check passed" || echo "\n✗ Health check failed"

scan:
	@echo "Scanning image for vulnerabilities..."
	@command -v trivy >/dev/null 2>&1 || { echo "Trivy not installed. Install from: https://github.com/aquasecurity/trivy/releases"; exit 1; }
	trivy image $(IMAGE_NAME):$(IMAGE_TAG)

push:
	@echo "Tagging image for registry..."
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	@echo "Pushing to $(REGISTRY)..."
	docker push $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)

deploy:
	@echo "Deploying to Kubernetes namespace: $(NAMESPACE)"
	@echo "Make sure you've updated the image reference in k8s/02-deployment.yaml first!"
	kubectl apply -f $(K8S_DIR)/
	@echo "Waiting for deployment..."
	kubectl rollout status deployment/flask-insights-hub -n $(NAMESPACE)

status:
	@echo "=== Kubernetes Deployment Status ==="
	@kubectl get all -n $(NAMESPACE)
	@echo ""
	@echo "=== Service Details ==="
	@kubectl get svc -n $(NAMESPACE) -o wide
	@echo ""
	@echo "=== Pod Details ==="
	@kubectl get pods -n $(NAMESPACE) -o wide

logs-k8s:
	kubectl logs -n $(NAMESPACE) -l app=flask-insights-hub -f

clean:
	@echo "Cleaning up local Docker resources..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) down -v
	docker rmi $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null || true
	@echo "Cleanup complete"

clean-k8s:
	@echo "Deleting Kubernetes resources..."
	kubectl delete namespace $(NAMESPACE) --ignore-not-found
	@echo "Cleanup complete"

.PHONY: build run stop logs test scan push deploy status logs-k8s clean clean-k8s
