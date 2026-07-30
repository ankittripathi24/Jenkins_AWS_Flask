# Kubernetes Manifests Reference Guide

This guide explains each Kubernetes manifest file and what it does.

## 📋 Quick Reference Table

| File | Purpose | Key Settings |
|------|---------|--------------|
| 01-namespace.yaml | Creates isolated namespace | `flask-app` |
| 02-deployment.yaml | Main app deployment | 3 replicas, resource limits, health checks |
| 03-service.yaml | External access (LoadBalancer) | Port 80 → 8080 |
| 04-hpa.yaml | Auto-scaling | 3-10 pods, 70% CPU / 80% memory triggers |
| 05-rbac.yaml | Security permissions | Service account + RBAC rules |
| 06-network-policy.yaml | Firewall rules | Allow ingress from nginx-ingress, allow DNS |
| 07-pdb.yaml | High availability | Minimum 2 pods available during disruptions |
| 08-configmap.yaml | Configuration | Environment variables |

---

## 📄 Detailed Manifest Descriptions

### 1. 01-namespace.yaml
**Purpose**: Creates an isolated namespace for all application resources

```yaml
metadata:
  name: flask-app              # All resources run in this namespace
  labels:
    name: flask-app
```

**Why**: Isolates your app from other workloads, makes cleanup easier (`kubectl delete namespace flask-app`)

**Key Points**:
- All pods, services, and config are in `flask-app` namespace
- Separate from `default`, `kube-system`, etc.
- Easy to delete everything with one command

---

### 2. 02-deployment.yaml ⭐ MOST IMPORTANT
**Purpose**: Defines how your Flask app runs in Kubernetes

**Key Sections**:

#### Replicas & Strategy
```yaml
replicas: 3                      # Run 3 instances
strategy:
  type: RollingUpdate           # Update one at a time
  rollingUpdate:
    maxSurge: 1                 # One extra pod during update
    maxUnavailable: 0           # Zero downtime updates
```

#### Container Configuration
```yaml
image: your-registry/flask-insights-hub:latest  # ⚠️ UPDATE THIS!
ports:
  - containerPort: 8080
```

#### Resource Limits (CRITICAL)
```yaml
resources:
  requests:                     # Minimum guaranteed resources
    memory: "128Mi"            # 128 megabytes
    cpu: "100m"                # 0.1 CPU cores
  limits:                       # Maximum resources allowed
    memory: "512Mi"            # 512 megabytes (crash if exceeded)
    cpu: "500m"                # 0.5 CPU cores
```

#### Health Checks
```yaml
livenessProbe:                 # Restart if unhealthy
  httpGet:
    path: /api/health
  periodSeconds: 30
  
readinessProbe:                # Remove from load balancer if unhealthy
  httpGet:
    path: /api/health
  periodSeconds: 10
```

#### Security
```yaml
securityContext:
  runAsNonRoot: true           # Don't run as root
  runAsUser: 1000              # Run as user 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL                       # Drop all Linux capabilities
```

**What to Change**:
- Line ~34: Update `image:` with your registry URL
- Example: `123456789.dkr.ecr.us-east-1.amazonaws.com/flask-insights-hub:latest`

---

### 3. 03-service.yaml
**Purpose**: Exposes your app to the outside world via LoadBalancer

```yaml
type: LoadBalancer              # Creates external IP/DNS
ports:
  - port: 80                    # External port (what users access)
    targetPort: 8080            # Internal pod port (Flask listens here)
```

**What It Does**:
- AWS: Creates Elastic Load Balancer, gives you an ELB DNS name
- Azure: Creates Azure Load Balancer, gives you a public IP
- Gets endpoint with: `kubectl get svc -n flask-app`

**Example Output**:
```
NAME                  TYPE          EXTERNAL-IP      PORT(S)
flask-insights-hub    LoadBalancer  a1b2c3d4.elb...  80:30123/TCP
```

---

### 4. 04-hpa.yaml
**Purpose**: Automatically scales pods based on load

```yaml
minReplicas: 3                  # Always run at least 3 pods
maxReplicas: 10                 # Never exceed 10 pods
metrics:
  - resource:
      name: cpu
      averageUtilization: 70    # Scale up if CPU > 70%
  - resource:
      name: memory
      averageUtilization: 80    # Scale up if memory > 80%
```

**Scaling Behavior**:
- **Scale Up**: When CPU hits 70% or memory hits 80%
  - Adds pods immediately (no delay)
  - Can add multiple pods at once
- **Scale Down**: When usage drops below thresholds
  - Waits 5 minutes before removing pods
  - Prevents flapping (rapid up/down scaling)

**Monitor with**:
```bash
kubectl get hpa -n flask-app --watch
kubectl describe hpa flask-insights-hub-hpa -n flask-app
```

---

### 5. 05-rbac.yaml
**Purpose**: Security - defines what permissions the app has

```yaml
ServiceAccount: flask-app-sa    # Identity for the pod
Role: flask-app-role           # List of allowed actions
RoleBinding                    # Connects account to role
```

**Permissions Granted**:
```yaml
rules:
- apiGroups: [""]
  resources: ["configmaps"]     # Can read ConfigMaps
  verbs: ["get", "list", "watch"]
- resources: ["secrets"]        # Can read Secrets
  verbs: ["get", "list"]
```

**Why This Matters**:
- Without RBAC, pods can do anything (dangerous!)
- This limits the pod to only reading config/secrets
- If the container is compromised, attacker has limited access

---

### 6. 06-network-policy.yaml
**Purpose**: Firewall - controls what network traffic is allowed

**Ingress Rules** (incoming traffic):
```yaml
from:
  - namespaceSelector:
      matchLabels:
        name: ingress-nginx     # Only from ingress controller
    ports:
    - port: 8080                # Only on port 8080
```

**Egress Rules** (outgoing traffic):
```yaml
to:
  - namespaceSelector: {}       # Can reach any namespace
    ports:
    - port: 443                 # HTTPS
    - port: 80                  # HTTP (for API calls)
  - podSelector:
      k8s-app: kube-dns
    ports:
    - port: 53                  # DNS
```

**What's Blocked Without This**:
- Ingress from other namespaces (except ingress-nginx)
- Random outbound connections

---

### 7. 07-pdb.yaml
**Purpose**: High availability - ensures service stays up during maintenance

```yaml
minAvailable: 2                 # At least 2 pods always running
```

**Scenarios**:
- If cluster node needs updates → Kubernetes wants to drain node
- Without PDB → All pods gone at once → Service down
- With PDB → Kubernetes ensures 2 pods stay up while updating others

**Example**:
```
3 pods running → Node needs update → K8s cordons node
  → Can only evict 1 pod (must keep 2 running)
  → Pod starts on another node
  → Update proceeds safely
```

---

### 8. 08-configmap.yaml
**Purpose**: Store configuration as key-value pairs

```yaml
data:
  PORT: "8080"
  BASE_PATH: ""
  WORKERS: "4"
  FLASK_ENV: "production"
```

**How Pods Use It**:
- Mounted as environment variables in the pod
- Can be updated without rebuilding container
- Changes trigger pod restart (via annotation in deployment)

**Update Configuration**:
```bash
# Edit in place
kubectl edit configmap flask-app-config -n flask-app

# Restart pods to apply changes
kubectl rollout restart deployment/flask-insights-hub -n flask-app
```

---

## 🔄 Deployment Order

Kubernetes usually figures out the order, but they're numbered for reference:

1. **01-namespace** → Creates the space
2. **05-rbac** → Sets up permissions (before deployment)
3. **02-deployment** → Starts the app (uses namespace from step 1)
4. **03-service** → Exposes the app
5. **04-hpa** → Enables auto-scaling
6. **06-network-policy** → Adds security
7. **07-pdb** → Ensures high availability
8. **08-configmap** → Provides configuration

**In Practice**: Just run `kubectl apply -f k8s/` - Kubernetes handles ordering.

---

## 📊 Resource Sizing Guide

### Current Configuration
```
Requests (guaranteed):  100m CPU, 128Mi memory
Limits (maximum):       500m CPU, 512Mi memory
```

### Scale Up (for production with heavy traffic)
Edit 02-deployment.yaml:
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "1"
```

### Scale Down (for dev/test)
```yaml
resources:
  requests:
    memory: "64Mi"
    cpu: "50m"
  limits:
    memory: "256Mi"
    cpu: "250m"
```

---

## 🔍 Viewing Manifests

### See what's deployed
```bash
# All resources
kubectl get all -n flask-app

# Just deployments
kubectl get deployments -n flask-app

# With more details
kubectl get deployment flask-insights-hub -n flask-app -o yaml
```

### Edit manifests after deployment
```bash
# Edit deployment
kubectl edit deployment flask-insights-hub -n flask-app

# Edit service
kubectl edit service flask-insights-hub -n flask-app

# Edit configmap
kubectl edit configmap flask-app-config -n flask-app
```

---

## ⚠️ Common Mistakes

1. **Forgot to update image URL** → Deployment fails pulling image
   - Fix: Update line 34 in 02-deployment.yaml

2. **Resource limits too low** → Pod crashes
   - Monitor: `kubectl top pods -n flask-app`
   - Fix: Increase limits in 02-deployment.yaml

3. **Changed YAML but pods didn't restart**
   - For Deployment/HPA changes: `kubectl rollout restart deployment/flask-insights-hub -n flask-app`
   - For ConfigMap changes: Manual restart needed (or use annotations)

4. **LoadBalancer service pending** → Image can't be pulled
   - Check: `kubectl describe service flask-insights-hub -n flask-app`
   - Logs: `kubectl logs -n flask-app -l app=flask-insights-hub`

---

## 🎯 Production Checklist

Before going to production:

- [ ] Updated image URL in 02-deployment.yaml
- [ ] Tested image builds and pushes
- [ ] Increased resource limits if needed
- [ ] Set up monitoring/logging (CloudWatch, DataDog, etc.)
- [ ] Configured TLS/Ingress for HTTPS
- [ ] Set up backup strategy
- [ ] Tested scaling (generate load, watch HPA scale)
- [ ] Documented how to rollback deployments
- [ ] Set up alerts for pod failures
- [ ] Reviewed NetworkPolicy rules for your use case

---

## 📚 Additional Resources

- [Kubernetes Deployment Docs](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Kubernetes Service Docs](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Horizontal Pod Autoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Pod Disruption Budgets](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)

