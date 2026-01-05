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

output "rds_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
