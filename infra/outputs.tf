output "alb_dns" {
  value = aws_lb.main.dns_name
}

output "application_url" {
  description = "URL to access the FastAPI application"
  value       = "http://${aws_lb.main.dns_name}"
}

output "prometheus_url" {
  description = "URL to access Prometheus in production"
  value       = "http://${aws_lb.main.dns_name}/prometheus"
}

output "grafana_url" {
  description = "URL to access Grafana in production"
  value       = "http://${aws_lb.main.dns_name}/grafana"
}

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

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.fastapi.name
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "security_group_rds_id" {
  description = "Security group ID for RDS"
  value       = aws_security_group.rds.id
}

output "security_group_alb_id" {
  description = "Security group ID for ALB"
  value       = aws_security_group.alb.id
}
