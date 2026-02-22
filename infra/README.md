# Terraform Infrastructure - Dyno Agent

## Quick Start

```bash
# 1. Configure AWS credentials
aws configure

# 2. Create variables file
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# 3. Deploy
terraform init
terraform plan
terraform apply

# 4. Get outputs
terraform output application_url
terraform output ecr_repository_url

# 5. Login to ECR and push image
$(terraform output -raw ecr_login_command)
docker build -t dyno-agent ../app
docker tag dyno-agent:latest $(terraform output -raw ecr_repository_url):latest
docker push $(terraform output -raw ecr_repository_url):latest

# 6. Cleanup
terraform destroy
```

## Infrastructure Components

### Enabled (Core Infrastructure)
- **VPC & Networking**: Public/private subnets, NAT Gateway, Internet Gateway
- **ECS Fargate**: FastAPI application (0.5 vCPU, 1GB RAM)
- **RDS PostgreSQL**: Database (db.t3.micro, 20GB)
- **ALB**: Application Load Balancer
- **ECR**: Docker registry
- **Secrets Manager**: API keys and credentials
- **CloudWatch**: Logs for FastAPI application
- **IAM Roles**: ECS execution and task roles

### Disabled (Can be enabled)
- **Prometheus + Grafana**: Production monitoring stack (see monitoring.tf.disabled)
- **EFS**: Persistent storage for monitoring (see monitoring.tf.disabled)

To enable monitoring, rename `monitoring.tf.disabled` to `monitoring.tf` and uncomment security groups in `security-groups.tf`.

## Important Notes

### Secret Recovery Window
The secret has `recovery_window_in_days = 0` to allow immediate recreation during development. **Change this to 7-30 days for production**.

### Cost Optimization Tips
- **NAT Gateway**: ~$32/month - Required for private subnets to reach internet
- **RDS db.t3.micro**: ~$15/month - Smallest production-capable instance
- **ECS Fargate**: ~$8/month per task (0.5 vCPU, 1GB RAM)
- **ALB**: ~$20/month - Required for HTTPS/path routing

**Total estimated cost: ~$75/month**

To reduce costs:
- Use `terraform destroy` when not testing
- Consider spot instances for non-critical workloads
- Use RDS Aurora Serverless v2 for variable workloads

### Monitoring Stack (Disabled by Default)
The Prometheus/Grafana stack adds complexity and cost:
- +2 ECS tasks (~$16/month)
- +EFS storage (~$5/month)
- +Increased ALB complexity

For simple deployments, use:
- **Local**: Docker Compose (prometheus + grafana)
- **Production**: CloudWatch + native AWS monitoring

Enable full monitoring stack when you need:
- Custom dashboards and PromQL queries
- Long-term metrics retention (30+ days)
- Advanced alerting rules

## File Structure

```
infra/
├── README.md                    # This file
├── provider.tf                  # Terraform and AWS provider config
├── variables.tf                 # Input variables
├── terraform.tfvars.example     # Example values (copy to terraform.tfvars)
├── network.tf                   # VPC, subnets, routing
├── security-groups.tf           # Security groups for ALB, ECS, RDS
├── iam.tf                       # IAM roles and policies
├── ecr.tf                       # Docker registry
├── rds.tf                       # PostgreSQL database
├── secrets.tf                   # AWS Secrets Manager
├── ecs.tf                       # ECS cluster, task definition, service
├── outputs.tf                   # Terraform outputs (URLs, endpoints)
└── monitoring.tf.disabled       # Optional: Prometheus + Grafana stack
```

## Common Issues

### Secret Already Exists
If you get "secret already exists" error after `terraform destroy`:
- Wait 7 days for automatic deletion, OR
- Manually delete: `aws secretsmanager delete-secret --secret-id dyno-agent-secrets --force-delete-without-recovery`

### ECS Task Not Starting
Check CloudWatch logs:
```bash
aws logs tail /ecs/dyno-agent-fastapi --follow
```

Common causes:
- Docker image not pushed to ECR
- Secrets not populated in Secrets Manager
- Database connection issues

### Database Connection Failed
Verify security groups:
```bash
# ECS should be in security group that can access RDS
terraform output security_group_rds_id
```

## Next Steps

After deploying:
1. Push Docker image to ECR (see outputs for login command)
2. Verify ECS task is running: `aws ecs list-tasks --cluster dyno-agent-cluster`
3. Check application health: `curl $(terraform output -raw application_url)/health`
4. Run database migrations (via ECS exec or bastion)
5. Configure DNS/domain name (optional)
6. Set up CI/CD pipeline (see GitHub Actions)

## Support

See main documentation:
- [INFRASTRUCTURE.md](../docs/INFRASTRUCTURE.md) - Detailed architecture
- [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) - Common issues
- [CICD.md](../docs/CICD.md) - Automated deployment
