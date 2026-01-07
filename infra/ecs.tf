############################
# ALB (Load Balancer)
############################

# Cria um Application Load Balancer público
# Ele quem expoee o serviço para a internet nao o container diretamente
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  load_balancer_type = "application"
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
}


# Target Group: para onde o ALB vai encaminhar as requisições
resource "aws_lb_target_group" "fastapi" {
  name        = "${var.project_name}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip" # obrigatório para ECS Fargate
  # Porque ECS Fargate não usa EC2, então o ALB aponta direto para IPs dos containers

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}


# Listener: ALB escuta na porta 80
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.fastapi.arn
  }
}


############################
# ECS Cluster
############################

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"
}

# Define como o container roda
# O cluster nao roda nada, só organiza os serviços
resource "aws_ecs_task_definition" "fastapi" {
  family                   = "${var.project_name}-task"
  network_mode             = "awsvpc" # obrigatório no Fargate
  requires_compatibilities = ["FARGATE"]
  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn = aws_iam_role.ecs_task.arn

  cpu    = "512"
  memory = "1024"

  container_definitions = jsonencode([
    {
      name  = "fastapi"
      image = aws_ecr_repository.fastapi.repository_url

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      secrets = [
        {
          name      = "PRODUCTION"
          valueFrom = "${aws_secretsmanager_secret.api.arn}:PRODUCTION::"
        },
        {
          name      = "HUGGING_FACE_HUB_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.api.arn}:HUGGING_FACE_HUB_TOKEN::"
        },
        {
          name      = "GEMINI_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.api.arn}:GEMINI_API_KEY::"
        },
        {
          name      = "DATABASE_URL_PROD"
          valueFrom = "${aws_secretsmanager_secret.api.arn}:DATABASE_URL_PROD::"
        },
        {
          name      = "DATABASE_URL_CHECKPOINTER_PROD"
          valueFrom = "${aws_secretsmanager_secret.api.arn}:DATABASE_URL_CHECKPOINTER_PROD::"
        },
        {
          name      = "JWT_SECRET"
          valueFrom = "${aws_secretsmanager_secret.api.arn}:JWT_SECRET::"
        }
      ]
    }
  ])
}


############################
# ECS Service
############################

# Service garante que o container fique sempre rodando
resource "aws_ecs_service" "fastapi" {
  name            = "${var.project_name}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.fastapi.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.fastapi.arn
    container_name   = "fastapi"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}
