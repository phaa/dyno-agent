output "alb_dns" {
  value = aws_lb.main.dns_name
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
