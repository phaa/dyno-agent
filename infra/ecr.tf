# Repositorio docker
resource "aws_ecr_repository" "fastapi" {
  name = "${var.project_name}-fastapi"
}
