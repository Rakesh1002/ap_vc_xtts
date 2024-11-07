# Deployment Guide

This guide covers the deployment of the Audio Processing API in production environments.

## Prerequisites

- Kubernetes cluster (1.19+)
- Helm (3.0+)
- kubectl configured with cluster access
- AWS account with S3 access
- Docker registry access

## Infrastructure Setup

### 1. Create Required Cloud Resources

```bash
Create S3 bucket
aws s3 mb s3://audio-processing-storage

Create IAM user for S3 access
aws iam create-user --user-name audio-processing-api
aws iam attach-user-policy --user-name audio-processing-api --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

### 2. Set Up HashiCorp Vault

```bash
Install Vault using Helm
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault

Initialize Vault
kubectl exec -it vault-0 -- vault operator init

Store the unseal keys and root token securely
```

### 3. Configure Database

```bash
Create PostgreSQL instance
kubectl apply -f k8s/postgres/

Initialize database
kubectl exec -it postgres-0 -- psql -U postgres -f /init/init.sql
```

## Application Deployment

### 1. Build and Push Docker Images

```bash
Build images
docker build -t audio-processing-api:latest .
docker build -t audio-processing-worker:latest -f Dockerfile.worker .
Push to registry
docker push audio-processing-api:latest
docker push audio-processing-worker:latest
```

### 2. Configure Secrets

```bash
Create Kubernetes secrets
kubectl create secret generic api-secrets \
--from-literal=postgres-password=<password> \
--from-literal=redis-password=<password> \
--from-literal=jwt-secret=<secret>

Configure Vault secrets
kubectl exec -it vault-0 -- vault kv put secret/audio-processing \
aws_access_key=<key> \
aws_secret_key=<secret>
```

### 3. Deploy Application Components

```bash
Deploy Redis
helm install redis bitnami/redis
Deploy API and workers
kubectl apply -f k8s/api/
kubectl apply -f k8s/worker/
Deploy monitoring stack
kubectl apply -f k8s/monitoring/
```

### 4. Configure Ingress and TLS

```bash
Install cert-manager
helm install cert-manager jetstack/cert-manager

Configure TLS certificates
kubectl apply -f k8s/tls/

Deploy ingress
kubectl apply -f k8s/ingress/
```

## Monitoring Setup

### 1. Deploy Prometheus and Grafana

```bash
helm install prometheus prometheus-community/kube-prometheus-stack
```

### 2. Import Dashboards

1. Access Grafana UI
2. Import dashboards from `grafana/dashboards/`
3. Configure alerts

## Scaling Configuration

### Horizontal Pod Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
name: api-hpa
spec:
scaleTargetRef:
apiVersion: apps/v1
kind: Deployment
name: audio-processing-api
minReplicas: 2
maxReplicas: 10
metrics:
type: Resource
resource:
name: cpu
target:
type: Utilization
averageUtilization: 70
```

### Worker Scaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
name: worker-hpa
spec:
scaleTargetRef:
apiVersion: apps/v1
kind: Deployment
name: audio-processing-worker
minReplicas: 2
maxReplicas: 20
metrics:
type: Resource
resource:
name: cpu
target:
type: Utilization
averageUtilization: 80
```

## Backup and Recovery

### Database Backups

```bash
Configure automated backups
kubectl apply -f k8s/backup/postgres-backup.yaml

Manual backup
kubectl exec -it postgres-0 -- pg_dump -U postgres > backup.sql
```

### S3 Backup

Configure S3 bucket versioning and lifecycle policies:

```bash
aws s3api put-bucket-versioning \
--bucket audio-processing-storage \
--versioning-configuration Status=Enabled
aws s3api put-bucket-lifecycle-configuration \
--bucket audio-processing-storage \
--lifecycle-configuration file://s3-lifecycle.json
```

## Maintenance

### Rolling Updates

```bash
Update API version
kubectl set image deployment/audio-processing-api \
audio-processing-api=audio-processing-api:new-version

Monitor rollout
kubectl rollout status deployment/audio-processing-api
```

### Database Migrations

```bash
Run migrations
kubectl exec -it api-deployment-xxx -- alembic upgrade head

Rollback if needed
kubectl exec -it api-deployment-xxx -- alembic downgrade -1
```

## Troubleshooting

### Common Issues

1. **Pod Crashes**

   ```bash
   kubectl logs pod/audio-processing-api-xxx
   kubectl describe pod/audio-processing-api-xxx
   ```

2. **Database Connection Issues**

   ```bash
   kubectl exec -it postgres-0 -- psql -U postgres
   ```

3. **Worker Queue Backlog**

   ```bash
   kubectl exec -it redis-0 -- redis-cli
   ```

### Monitoring Checks

1. Check API health:

   ```bash
   curl https://api.example.com/health
   ```

2. View metrics:

   ```bash
   kubectl port-forward svc/prometheus 9090:9090
   ```

3. Check logs:

   ```bash
   kubectl logs -l app=audio-processing-api --tail=100
   ```

## Security Considerations

1. **Network Policies**

   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: api-network-policy
   spec:
     podSelector:
       matchLabels:
         app: audio-processing-api
     ingress:
       - from:
           - podSelector:
               matchLabels:
                 app: ingress-nginx
     egress:
       - to:
           - podSelector:
               matchLabels:
                 app: postgres
           - podSelector:
               matchLabels:
                 app: redis
   ```

2. **Pod Security Policies**
3. **Regular Security Audits**
4. **Secret Rotation**

## Performance Tuning

1. **Resource Limits**

```yaml
resources:
  limits:
    cpu: "2"
    memory: "4Gi"
  requests:
    cpu: "500m"
    memory: "1Gi"
```

2. **Database Optimization**

3. **Cache Configuration**

4. **Worker Queue Settings**
