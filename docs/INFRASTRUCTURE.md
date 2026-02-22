# AWS Infrastructure - Dyno Agent

## Important Disclaimer (Scope & Intent)

> ⚠️ This infrastructure is designed for **demonstration, learning, and portfolio purposes**.
>  
> Several production best practices are **intentionally simplified** and clearly documented
> to prioritize clarity, learning, and cost awareness over enterprise-grade completeness.

Examples of intentional simplifications:
- Single-instance ECS services
- No auto-scaling policies
- Monitoring stack (Prometheus/Grafana) disabled by default (use docker-compose locally)
- Basic authentication for Grafana (when enabled)
- Simplified secrets handling for local development
- NAT Gateway (cost ~$32/month) - consider alternatives for dev/test

All such decisions are **explicit, conscious trade-offs**, not omissions.

---

## Overview

Terraform is used to bootstrap and evolve the production infrastructure.

Its responsibilities include creating and managing long-lived AWS resources such as
networking (VPC, subnets), compute orchestration (ECS, ALB), persistent storage (RDS),
IAM roles, and secret containers (AWS Secrets Manager), but not the application secrets
themselves.

**Core Infrastructure (Always Enabled)**:
- **ECS Fargate** - FastAPI application (0.5 vCPU, 1GB RAM)
- **RDS PostgreSQL** - Database (db.t3.micro, 20GB)
- **ALB** - Application Load Balancer
- **ECR** - Docker registry
- **VPC** - Networking with public/private subnets
- **CloudWatch** - Logs for application
- **Secrets Manager** - Runtime secrets

**Optional Infrastructure (Disabled by Default)**:
- **Prometheus + Grafana** - Production monitoring stack (see `monitoring.tf.disabled`)
- **EFS** - Persistent storage for monitoring data

For local development, use `docker-compose.yml` which includes Prometheus and Grafana.

Application deployments, container builds, and image publishing are handled exclusively
by the CI/CD pipeline, which updates running services without modifying the underlying
infrastructure.

Runtime secrets (e.g. database credentials, external API keys such as LLM providers)
are never stored in Terraform state or configuration files in production.
Instead, they are managed by AWS Secrets Manager and accessed at runtime via
IAM-scoped permissions from the application containers.

This separation ensures:
- Clear ownership boundaries between infrastructure and application lifecycle
- Secure secret handling with no dependency on developer machines
- Repeatable deployments and predictable runtime behavior

## Infrastructure Components

### Core Components (Always Deployed)
- **ECS Fargate**: FastAPI application container (0.5 vCPU, 1GB RAM)
- **RDS PostgreSQL**: Database (db.t3.micro, 20GB encrypted)
- **ALB**: Application Load Balancer (HTTP only, path-based routing)
- **ECR**: Docker container registry
- **VPC**: Custom VPC with public/private subnets across 2 AZs
- **NAT Gateway**: Internet access for private subnets
- **Secrets Manager**: Runtime secrets (DB credentials, API keys)
- **CloudWatch Logs**: Application logs (7-day retention)
- **IAM Roles**: ECS execution and task roles

### Optional Components (Disabled by Default)
- **Prometheus + Grafana**: Production monitoring stack
- **EFS**: Persistent storage for monitoring data

To enable monitoring stack: `mv infra/monitoring.tf.disabled infra/monitoring.tf`

For development, use the included `docker-compose.yml` with Prometheus and Grafana.

## Architecture Overview

```mermaid
graph TB
    subgraph "Internet"
        Users[Users]
    end

    subgraph "AWS VPC"
        subgraph "Public Subnets"
            ALB[Application Load Balancer]
            NAT[NAT Gateway]
        end

        subgraph "Private Subnets"
            subgraph "ECS Fargate Cluster"
                FastAPI[FastAPI App<br/>0.5 vCPU, 1GB RAM]
            end

            RDS[(RDS PostgreSQL<br/>db.t3.micro, 20GB)]
        end
    end

    subgraph "AWS Services"
        ECR[ECR Registry]
        Secrets[Secrets Manager]
        CloudWatch[CloudWatch Logs]
    end

    Users --> ALB
    ALB --> FastAPI
    FastAPI --> RDS
    FastAPI --> Secrets
    FastAPI --> CloudWatch
    FastAPI -.-> NAT
    
    style FastAPI fill:#e3f2fd
    style RDS fill:#fff3e0
    style Secrets fill:#f3e5f5
```

**Note**: For monitoring (Prometheus/Grafana), use the local `docker-compose.yml` during development.
Production monitoring stack is available in `monitoring.tf.disabled` and can be enabled when needed.

---

## Configuration & Secrets Strategy

### Dual Secrets Strategy (Intentional)

**Local Development**
- terraform.tfvars
- .env files
- Docker Compose

**Production**
- AWS Secrets Manager
- Injected via ECS task definitions
- IAM-scoped access only

> Secrets stored in `terraform.tfvars` are **never intended for production use**.
> Production secrets are managed exclusively through AWS Secrets Manager.

This dual approach mirrors real-world engineering trade-offs:
- Developer Experience locally
- Security and compliance in production

---

### Environment Detection Flow

```mermaid
flowchart LR
    Start([Application Start]) --> Check{PRODUCTION?}
    
    Check -->|false| Dev[Development Mode]
    Check -->|true| Prod[Production Mode]
    
    Dev --> DockerDB[(Docker PostgreSQL<br/>db:5432<br/>sslmode=disable)]
    Prod --> AWSRDS[(AWS RDS<br/>rds-endpoint:5432<br/>sslmode=require)]
    
    DockerDB --> SQLAlchemy[SQLAlchemy<br/>asyncpg driver]
    DockerDB --> Checkpointer[LangGraph<br/>psycopg2 driver]
    
    AWSRDS --> SQLAlchemy2[SQLAlchemy<br/>asyncpg driver]
    AWSRDS --> Checkpointer2[LangGraph<br/>psycopg2 driver]
    
    style Dev fill:#e1f5fe
    style Prod fill:#fff3e0
    style DockerDB fill:#e8f5e8
    style AWSRDS fill:#fff8e1
```

**Key Features**:
- **Single Variable Control**: `PRODUCTION=true/false` determines entire environment
- **Automatic SSL**: Production uses `sslmode=require`, development uses `sslmode=disable`
- **Dual Drivers**: SQLAlchemy (`asyncpg`) + LangGraph (`psycopg2`) for optimal performance
- **Zero Configuration**: No hardcoded credentials, all from environment variables

- **Application**: Single ECS task (desired_count = 1)
- **Database**: Basic RDS instance (20GB storage)
- **Monitoring**: Prometheus + Grafana on ECS with EFS storage
- **Load Balancer**: ALB with path-based routing (`/`, `/prometheus`, `/grafana`)
- **Network**: Private subnets for services, public subnets for ALB

## Quick Setup

### Prerequisites
- AWS CLI configured (`aws configure`)
- Terraform >= 1.3.0
- Docker (for building and pushing images)

### Deployment Steps

**Environment Configuration**: The system uses a single `PRODUCTION` boolean variable to automatically configure database connections and other environment-specific settings.

```mermaid
flowchart TD
    EnvVar[PRODUCTION Environment Variable] --> Decision{Value?}
    
    Decision -->|false| DevConfig[Development Configuration]
    Decision -->|true| ProdConfig[Production Configuration]
    
    DevConfig --> DevDB[DATABASE_URL<br/>postgresql+asyncpg://...@db:5432/...]
    DevConfig --> DevCheck[DATABASE_URL_CHECKPOINTER<br/>postgresql://...@db:5432/...?sslmode=disable]
    
    ProdConfig --> ProdDB[DATABASE_URL_PROD<br/>postgresql+asyncpg://...@rds-endpoint:5432/...]
    ProdConfig --> ProdCheck[DATABASE_URL_CHECKPOINTER_PROD<br/>postgresql://...@rds-endpoint:5432/...?sslmode=require]
    
    DevDB --> App1[FastAPI Application]
    DevCheck --> App1
    ProdDB --> App2[FastAPI Application]
    ProdCheck --> App2
    
    style DevConfig fill:#e1f5fe
    style ProdConfig fill:#fff3e0
    style EnvVar fill:#f3e5f5
```

**Development Setup (.env)**:
```bash
PRODUCTION=false
DATABASE_URL=postgresql+asyncpg://dyno_user:dyno_pass@db:5432/dyno_db
DATABASE_URL_CHECKPOINTER=postgresql://dyno_user:dyno_pass@db:5432/dyno_db?sslmode=disable
```

**Production Setup (terraform.tfvars)**:
```bash
production = true
# Other production variables...
```

**Why This Approach?**
- **Zero Configuration Errors**: Single variable controls all environment behavior
- **Automatic SSL**: Production uses `sslmode=require`, development uses `sslmode=disable`
- **Driver Optimization**: SQLAlchemy uses `asyncpg`, LangGraph checkpointer uses `psycopg2`
- **AWS Integration**: Production variables automatically injected via Secrets Manager

1. **Configure AWS credentials**:
```bash
aws configure
```

2. **Create variables file**:
```bash
cd infra/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values:
# - db_password (strong password for RDS)
# - gemini_api_key (optional, for LLM)
# - huggingface_token (optional, for models)
# - jwt_secret (random string for JWT auth)
```

3. **Deploy infrastructure**:
```bash
terraform init
terraform plan    # Review changes
terraform apply   # Type 'yes' to confirm
```

4. **Build and push Docker image**:
```bash
# Login to ECR
$(terraform output -raw ecr_login_command)

# Build and tag image
cd ../app
docker build -t dyno-agent .
docker tag dyno-agent:latest $(cd ../infra && terraform output -raw ecr_repository_url):latest

# Push to ECR
docker push $(cd ../infra && terraform output -raw ecr_repository_url):latest
```

### Manual Deploy (Without CI/CD)

If you want to test manually (no CI/CD), follow these steps after `terraform apply`:

```bash
# 1) Login to ECR
cd infra
$(terraform output -raw ecr_login_command)

# 2) Build image locally
cd ../app
docker build -t dyno-agent .

# 3) Tag image for ECR
ECR_URL=$(cd ../infra && terraform output -raw ecr_repository_url)
docker tag dyno-agent:latest "$ECR_URL":latest

# 4) Push image to ECR
docker push "$ECR_URL":latest

# 5) Force ECS to pull the new image
aws ecs update-service \
  --cluster dyno-agent-cluster \
  --service dyno-agent-service \
  --force-new-deployment

# 6) Verify health
curl $(cd ../infra && terraform output -raw application_url)/health
```

5. **Verify deployment**:
```bash
# Get application URL
terraform output application_url

# Check health
curl $(terraform output -raw application_url)/health

# View logs
aws logs tail /ecs/dyno-agent-fastapi --follow
```

6. **Access application**:
```bash
open $(terraform output -raw application_url)
```

7. **Cleanup** (when done testing):
```bash
terraform destroy  # Type 'yes' to confirm
```

## Important Outputs

After `terraform apply`, you'll get these outputs:

## Important Outputs

After `terraform apply`, you'll get these outputs:

- `application_url` → FastAPI application (http://your-alb-dns.amazonaws.com)
- `ecr_repository_url` → Docker registry URL for image push
- `ecr_login_command` → Command to login to ECR
- `rds_endpoint` → Database endpoint (for migrations/debugging)
- `vpc_id` → VPC ID for reference
- `private_subnet_ids` → Private subnet IDs
- `public_subnet_ids` → Public subnet IDs
- `secret_arn` → Secrets Manager ARN
- `ecs_cluster_name` → ECS cluster name
- `ecs_service_name` → ECS service name

**Note**: Prometheus/Grafana URLs are only available if you enable `monitoring.tf`.

## Current Configuration

### Cost Breakdown (Estimated Monthly)
- **RDS db.t3.micro**: ~$15/month (20GB storage, no backups)
- **ECS Fargate** (1 task, 0.5 vCPU, 1GB): ~$8/month
- **NAT Gateway**: ~$32/month (+ data transfer)
- **ALB**: ~$20/month (+ data transfer)
- **Secrets Manager**: ~$0.40/month (1 secret)
- **CloudWatch Logs**: ~$1/month (7-day retention, low volume)

**Total: ~$75-80/month**

> 💡 **Cost Savings Tip**: Use `terraform destroy` when not actively testing to avoid charges.
> The entire stack can be recreated in ~10 minutes.

### Monitoring Strategy

**Development (Recommended)**:
- Use `docker-compose.yml` with Prometheus + Grafana locally
- Free, fast, easy to use
- Access at http://localhost:3000 (Grafana) and http://localhost:9090 (Prometheus)

**Production (Optional)**:
- Enable `monitoring.tf` for ECS-based Prometheus/Grafana
- Adds ~$20/month (2 ECS tasks + EFS storage)
- Use CloudWatch for basic monitoring (built-in, low cost)
- Use CloudWatch Alarms for critical alerts

### CloudWatch Integration

In addition to CloudWatch, you can use Prometheus for high-frequency metrics during development.

This hybrid approach allows:
- High-frequency, low-cost metrics via Prometheus (local)
- Low-frequency, business-critical metrics via CloudWatch (production)
- Native AWS alarms and dashboards for key KPIs

### ECS Services

**FastAPI Application**:
- **CPU**: 512 (0.5 vCPU)
- **Memory**: 1024 MB (1GB)
- **Desired Count**: 1 instance
- **Path**: `/` (all requests)
- **Health Check**: `/health` endpoint
- **Logs**: CloudWatch Logs (/ecs/dyno-agent-fastapi, 7-day retention)

**Optional Monitoring Services** (disabled by default, see `monitoring.tf.disabled`):
- Prometheus: 0.5 vCPU, 1GB RAM, EFS storage, path `/prometheus`
- Grafana: 0.5 vCPU, 1GB RAM, EFS storage, path `/grafana`

### RDS PostgreSQL
- **Instance**: db.t3.micro (2 vCPU, 1GB RAM)
- **Engine**: PostgreSQL 14.7 (free tier compatible)
- **Storage**: 20GB encrypted (GP2)
- **Backups**: 0 days (free tier limitation) - change to 7+ on paid tier
- **Subnet**: Private subnets only
- **Security**: Security group allows ECS only

### Security
- **JWT authentication** via AWS Secrets Manager
- **API keys** stored in Secrets Manager (not in code/configs)
- **Private subnets** for ECS and RDS (no direct internet access)
- **Security groups** with least privilege (ECS → RDS only on port 5432)
- **RDS encryption** at rest (KMS)
- **Secrets rotation**: Manual (can be automated with Lambda)
- **Secret recovery**: 0 days (dev/test) - change to 7-30 for production

## Estimated Costs

## Estimated Costs

### Monthly AWS Costs (Core Infrastructure)
- **RDS db.t3.micro**: ~$15/month (20GB storage)
- **ECS Fargate** (1 task, 0.5 vCPU, 1GB): ~$8/month
- **NAT Gateway**: ~$32/month (fixed) + $0.045/GB data transfer
- **ALB**: ~$20/month (fixed) + $0.008/LCU-hour
- **ECR**: ~$1/month (500MB storage)
- **Secrets Manager**: ~$0.40/month (1 secret)
- **CloudWatch Logs**: ~$1/month (7-day retention, low traffic)
- **Data Transfer**: ~$2-5/month (varies by usage)

**Total: ~$75-80/month**

### Optional Monitoring Stack (monitoring.tf)
- **ECS Fargate** (2 additional tasks): +$16/month
- **EFS**: +$5/month (10GB, provisioned throughput)
- **ALB routing**: +$2/month (additional LCU usage)

**Total with monitoring: ~$98-103/month**

### Cost Comparison
- **Without monitoring**: ~$75/month (use CloudWatch + local Prometheus)
- **With Prometheus/Grafana on ECS**: ~$100/month
- **CloudWatch Metrics only** (high-frequency): +$500-1,500/month ❌

> 💡 **Recommendation**: Use `docker-compose.yml` for development monitoring (free).
> Enable production monitoring stack only when you need persistent dashboards in AWS.

## Production Enhancements

## Production Enhancements

### Current State

This infrastructure is **production-capable** but **intentionally simplified** for:
- Learning and demonstration purposes
- Cost-effective testing and development
- Easy understanding and modification

**What's included**:
- ✅ Encrypted database (RDS with encryption at rest)
- ✅ Private networking (ECS and RDS in private subnets)
- ✅ Secret management (AWS Secrets Manager)
- ✅ Application logs (CloudWatch)
- ✅ Health checks (ALB health checks)
- ✅ Database backups (7-day retention)

**What's simplified**:
- ⚠️ Single ECS task (no auto-scaling)
- ⚠️ HTTP only (no HTTPS/SSL)
- ⚠️ Single-AZ RDS (no Multi-AZ failover)
- ⚠️ Basic monitoring (CloudWatch only)
- ⚠️ No WAF or DDoS protection

### Enabling Production Monitoring Stack

To enable Prometheus + Grafana on AWS:

```bash
cd infra/
mv monitoring.tf.disabled monitoring.tf

# Uncomment security groups in security-groups.tf
# Search for "# resource \"aws_security_group\" \"monitoring\"" and uncomment

terraform plan
terraform apply
```

**Benefits**:
- Persistent metrics across deployments
- Custom dashboards accessible from anywhere
- PromQL queries for advanced analysis
- 30-day retention (configurable)

**Trade-offs**:
- +$20-25/month additional cost
- More complex infrastructure
- Requires EFS management

### Future Production Enhancements

For enterprise deployment, consider adding:
- **Auto-scaling policies** for ECS services
- **Multi-AZ RDS deployment** for high availability
- **HTTPS/SSL certificates** for secure access
- **Prometheus Alertmanager** for advanced alerting
- **Backup strategies** for EFS monitoring data
- **Blue-green deployment** for zero-downtime updates
- **RDS Proxy** for connection pooling
- **WAF integration** for application security

### Monitoring Architecture Benefits

**For Recruiters**: This implementation demonstrates:
- **Cost Optimization**: Reduced monitoring costs by 95%
- **Production Readiness**: Enterprise-grade monitoring stack
- **AWS Expertise**: ECS, EFS, ALB, and security best practices
- **Operational Excellence**: Persistent monitoring with disaster recovery

---

## Production Operations (AWS RDS)

**Database management when deployed to AWS:**

> **Important**: In production, the system uses AWS RDS PostgreSQL, not local Docker containers. Database operations require different approaches.

### Database Migrations (Production)
```bash
# Option 1: Via ECS Task (Recommended)
# Run migration as one-time ECS task
aws ecs run-task \
  --cluster dyno-agent-cluster \
  --task-definition dyno-agent-migration \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"

# Option 2: Via Local Connection (Development)
# Connect to RDS from local machine (requires VPN/bastion)
export DATABASE_URL="postgresql://dyno_user:password@rds-endpoint:5432/dyno_db"
cd app && alembic upgrade head

# Option 3: Via CI/CD Pipeline (Automated)
# Migrations run automatically during deployment
# See: .github/workflows/deploy.yml
```

### Database Access (Production)
```bash
# Option 1: Via ECS Exec (Recommended)
# Connect to running container and access database
aws ecs execute-command \
  --cluster dyno-agent-cluster \
  --task <task-id> \
  --container fastapi \
  --interactive \
  --command "/bin/bash"

# Inside container:
psql $DATABASE_URL

# Option 2: Via Bastion Host (Secure)
# Set up bastion host in public subnet
# SSH tunnel to RDS through bastion
ssh -L 5432:rds-endpoint:5432 ec2-user@bastion-host
psql -h localhost -p 5432 -U dyno_user dyno_db

# Option 3: Via AWS RDS Proxy (Enterprise)
# Use RDS Proxy for connection pooling and security
psql -h rds-proxy-endpoint -p 5432 -U dyno_user dyno_db
```

### Production Database Operations
```bash
# View database logs
aws rds describe-db-log-files --db-instance-identifier dyno-agent-db
aws rds download-db-log-file-portion --db-instance-identifier dyno-agent-db --log-file-name error/postgresql.log

# Create database snapshot
aws rds create-db-snapshot \
  --db-instance-identifier dyno-agent-db \
  --db-snapshot-identifier dyno-agent-backup-$(date +%Y%m%d)

# Monitor database performance
aws rds describe-db-instances --db-instance-identifier dyno-agent-db
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=dyno-agent-db

# Scale database (if needed)
aws rds modify-db-instance \
  --db-instance-identifier dyno-agent-db \
  --db-instance-class db.t3.small \
  --apply-immediately
```

### Application Operations (Production)
```bash
# View application logs
aws logs tail /ecs/dyno-agent --follow

# Scale ECS service
aws ecs update-service \
  --cluster dyno-agent-cluster \
  --service dyno-agent-service \
  --desired-count 3

# Deploy new version (via CI/CD)
git tag v1.2.0
git push origin v1.2.0
# GitHub Actions automatically builds and deploys

# Manual deployment (emergency)
aws ecs update-service \
  --cluster dyno-agent-cluster \
  --service dyno-agent-service \
  --force-new-deployment
```

### Monitoring Production
```bash
# CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace DynoAgent/Production \
  --metric-name AllocationRequests

# Application health
curl https://your-alb-endpoint.amazonaws.com/health

# Database health
aws rds describe-db-instances \
  --db-instance-identifier dyno-agent-db \
  --query 'DBInstances[0].DBInstanceStatus'
```

---

## Common Issues & Troubleshooting

### 1. Secret Already Exists Error

**Problem**: `terraform apply` fails with "secret already exists"

**Solution**:
```bash
# Force delete (dev/test only)
aws secretsmanager delete-secret \
  --secret-id dyno-agent-secrets \
  --force-delete-without-recovery
```

### 2. ECS Task Not Starting

**Diagnosis**:
```bash
# Check logs
aws logs tail /ecs/dyno-agent-fastapi --follow

# List tasks
aws ecs list-tasks --cluster dyno-agent-cluster
```

**Common Causes**:
- Docker image not pushed to ECR → Run `terraform output -raw ecr_login_command`
- Secrets not populated → Check AWS Secrets Manager
- Database connection failed → Verify security groups

### 3. High NAT Gateway Costs

**Solutions**:
- Use VPC endpoints for AWS services (S3, ECR)
- Reduce unnecessary outbound traffic
- Consider NAT instances for dev/test

### 4. Cannot Access Application

**Diagnosis**:
```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups \
    --names dyno-agent-tg --query 'TargetGroups[0].TargetGroupArn' --output text)
```

**Solutions**:
- Wait 2-3 minutes after deployment for health checks
- Verify ECS task is running: `aws ecs list-tasks --cluster dyno-agent-cluster`
- Check application logs in CloudWatch

---

## Additional Resources

- [infra/README.md](../infra/README.md) - Quick reference guide
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Detailed troubleshooting
- [CICD.md](./CICD.md) - Automated deployment
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/intro.html)