resource "aws_db_instance" "postgres" {
  identifier = "${var.project_name}-db"

  engine         = "postgres"
  engine_version = "15.5"
  instance_class = "db.t3.micro"

  allocated_storage = 20
  storage_encrypted = true

  username = "dyno_user"
  password = var.db_password
  db_name  = "dyno_db"

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  skip_final_snapshot = true
  deletion_protection = false

  # Automated backups configuration
  backup_retention_period = var.backup_retention_days
  backup_window           = var.backup_window
  maintenance_window      = var.maintenance_window

  tags = {
    Name = "${var.project_name}-database"
  }
}

resource "aws_db_subnet_group" "main" {
  subnet_ids = aws_subnet.private[*].id
}
