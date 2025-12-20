# AWS Infrastructure - Dyno Agent

Terraform for deploying Dyno-Agent project on AWS using:
- **ECS Fargate** (containers)
- **RDS PostgreSQL** (database)
- **ALB** (load balancer)
- **ECR** (Docker registry)

## Quick Setup

1. **Configure AWS credentials**:
```bash
aws configure
```

2. **Create variables file**:
```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

3. **Deploy**:
```bash
terraform init
terraform plan
terraform apply
```

4. **Cleanup**:
```bash
terraform destroy
```

## Important Outputs

- `alb_dns` → Application URL
- `ecr_repository_url` → For Docker image push
- `rds_endpoint` → Database endpoint

## Estimated Costs

- RDS t3.micro: ~$15/month
- ECS Fargate: ~$10/month
- ALB: ~$20/month
- **Total: ~$45/month**

> 💡 **Tip**: Use `terraform destroy` after testing to avoid costs!