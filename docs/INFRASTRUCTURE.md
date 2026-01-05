# AWS Infrastructure - Dyno Agent

Terraform for deploying Dyno-Agent project on AWS using:
- **ECS Fargate** (containers - 0.5 vCPU, 1GB RAM)
- **RDS PostgreSQL** (database - db.t3.micro)
- **ALB** (load balancer)
- **ECR** (Docker registry)
- **VPC** (networking with public/private subnets)

## Architecture Overview

- **Single ECS task** (desired_count = 1)
- **Basic RDS instance** (20GB storage, no auto-scaling)
- **Simple ALB** (HTTP only, health checks on /health)
- **Private subnets** for ECS and RDS
- **Public subnets** for ALB

## Quick Setup

1. **Configure AWS credentials**:
```bash
aws configure
```

2. **Create variables file**:
```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values:
# - db_password
# - gemini_api_key
# - jwt_secret
```

3. **Deploy**:
```bash
cd infra/
terraform init
terraform plan
terraform apply
```

4. **Get outputs**:
```bash
terraform output
```

5. **Cleanup**:
```bash
terraform destroy
```

## Important Outputs

- `alb_dns` → Application URL (http://your-alb-dns.amazonaws.com)
- `ecr_repository_url` → For Docker image push
- `rds_endpoint` → Database endpoint
- `vpc_id` → VPC ID for reference
- `private_subnet_ids` → Private subnet IDs

## Current Configuration

### ECS Fargate
- **CPU**: 512 (0.5 vCPU)
- **Memory**: 1024 MB (1GB)
- **Desired Count**: 1 instance
- **No auto-scaling** (basic setup)

### RDS PostgreSQL
- **Instance**: db.t3.micro
- **Engine**: PostgreSQL 15.5
- **Storage**: 20GB encrypted
- **No backups** (skip_final_snapshot = true)
- **No monitoring** (basic setup)

### Security
- **JWT authentication** via AWS Secrets Manager
- **API keys** stored in Secrets Manager
- **Private subnets** for backend services
- **Security groups** with minimal required access

## Estimated Costs

- **RDS t3.micro**: ~$15/month
- **ECS Fargate (0.5 vCPU, 1GB)**: ~$8/month
- **ALB**: ~$20/month
- **Data transfer & storage**: ~$2/month
- **Total**: ~$45/month

> 💡 **Tip**: Use `terraform destroy` after testing to avoid costs!

## Production Enhancements (future tasks)

For production deployment, I'll consider adding:
- Auto-scaling policies
- Multi-AZ RDS deployment
- HTTPS/SSL certificates
- CloudWatch monitoring
- Backup strategies
- Blue-green deployment

These are currently in the **planned features** list.