output "alb_dns" {
  value = aws_lb.main.dns_name
}

output "application_url" {
  description = "URL to access the FastAPI application"
  value       = "http://${aws_lb.main.dns_name}"
}

# Note: Prometheus/Grafana outputs are disabled. To enable monitoring stack,
# rename monitoring.tf.disabled to monitoring.tf and uncomment outputs below:
# output "prometheus_url" {
#   description = "URL to access Prometheus in production"
#   value       = "http://${aws_lb.main.dns_name}/prometheus"
# }
# output "grafana_url" {
#   description = "URL to access Grafana in production"
#   value       = "http://${aws_lb.main.dns_name}/grafana"
# }

output "ecr_repository_url" {
  value = aws_ecr_repository.fastapi.repository_url
}

output "ecr_repository_name" {
  description = "Name of the ECR repository"
  value       = aws_ecr_repository.fastapi.name
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.postgres.db_name
}

output "rds_username" {
  description = "RDS master username"
  value       = aws_db_instance.postgres.username
  sensitive   = true
}

output "rds_port" {
  description = "RDS database port"
  value       = aws_db_instance.postgres.port
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "vpc_id" {
  description = "VPC ID for reference"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "secret_arn" {
  description = "ARN of the secrets manager secret"
  value       = aws_secretsmanager_secret.api.arn
  sensitive   = true
}

output "ecr_login_command" {
  description = "Command to login to ECR"
  value       = "aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${aws_ecr_repository.fastapi.repository_url}"
}

output "ecs_service_name" {
  description = "ECS service name for the FastAPI application"
  value       = aws_ecs_service.fastapi.name
}

output "security_group_rds_id" {
  description = "Security group ID for RDS"
  value       = aws_security_group.rds.id
}

output "security_group_alb_id" {
  description = "Security group ID for ALB"
  value       = aws_security_group.alb.id
}
