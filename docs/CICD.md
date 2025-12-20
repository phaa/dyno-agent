# CI/CD Pipeline - GitHub Actions

Automated pipeline for build and deploy to AWS ECR.

## Initial Setup

### 1. GitHub Secrets
Configure in repository: `Settings > Secrets and variables > Actions`

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

### 2. IAM Permissions
Create an IAM user with policies:
- `AmazonEC2ContainerRegistryPowerUser`
- `AmazonECS_FullAccess`

### 3. Deploy Infrastructure (REQUIRED FIRST)
```bash
cd infra/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your real values
terraform init
terraform apply
```

⚠️ **IMPORTANT**: Infrastructure must exist BEFORE first push!

### 4. First Push (AFTER infrastructure)
```bash
git add .
git commit -m "feat: add CI/CD pipeline"
git push origin main
```

## How It Works

1. **Trigger**: Push to `main` branch
2. **Build**: Creates Docker image
3. **Push**: Sends to ECR with tags:
   - `latest`
   - `commit-hash`
4. **Deploy**: Forces new deployment on ECS

## Monitoring

- **GitHub Actions**: Pipeline logs
- **AWS ECS**: Service status
- **AWS CloudWatch**: Application logs

## Rollback

```bash
# Via AWS CLI
aws ecs update-service \
  --cluster dyno-agent-cluster \
  --service dyno-agent-service \
  --task-definition dyno-agent-task:PREVIOUS_REVISION
```