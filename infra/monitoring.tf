############################
# EFS for Persistent Storage
############################

# EFS file system for Prometheus data and Grafana dashboards
resource "aws_efs_file_system" "monitoring" {
  creation_token = "${var.project_name}-monitoring-efs"
  
  performance_mode = "generalPurpose"
  throughput_mode  = "provisioned"
  provisioned_throughput_in_mibps = 20
  
  encrypted = true
  
  tags = {
    Name = "${var.project_name}-monitoring-efs"
  }
}

# EFS mount targets in private subnets
resource "aws_efs_mount_target" "monitoring" {
  count = length(aws_subnet.private)
  
  file_system_id  = aws_efs_file_system.monitoring.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs.id]
}

# EFS access points for Prometheus and Grafana
resource "aws_efs_access_point" "prometheus" {
  file_system_id = aws_efs_file_system.monitoring.id
  
  posix_user {
    uid = 65534  # nobody user
    gid = 65534  # nobody group
  }
  
  root_directory {
    path = "/prometheus"
    creation_info {
      owner_uid   = 65534
      owner_gid   = 65534
      permissions = "755"
    }
  }
  
  tags = {
    Name = "${var.project_name}-prometheus-access-point"
  }
}

resource "aws_efs_access_point" "grafana" {
  file_system_id = aws_efs_file_system.monitoring.id
  
  posix_user {
    uid = 472  # grafana user
    gid = 472  # grafana group
  }
  
  root_directory {
    path = "/grafana"
    creation_info {
      owner_uid   = 472
      owner_gid   = 472
      permissions = "755"
    }
  }
  
  tags = {
    Name = "${var.project_name}-grafana-access-point"
  }
}

############################
# Prometheus ECS Service
############################

# Prometheus task definition
resource "aws_ecs_task_definition" "prometheus" {
  family                   = "${var.project_name}-prometheus"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn           = aws_iam_role.ecs_task.arn
  
  cpu    = "512"
  memory = "1024"
  
  volume {
    name = "prometheus-data"
    
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.monitoring.id
      transit_encryption = "ENABLED"

      authorization_config {
        access_point_id = aws_efs_access_point.prometheus.id
        iam             = "ENABLED"
      }
    }
  }

  volume {
    name = "prometheus-config"

    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.monitoring.id
      transit_encryption = "ENABLED"

      authorization_config {
        access_point_id = aws_efs_access_point.prometheus.id
        iam             = "ENABLED"
      }
    }
  }

  
  container_definitions = jsonencode([
    {
      name  = "prometheus"
      image = "prom/prometheus:latest"
      
      portMappings = [
        {
          containerPort = 9090
          protocol      = "tcp"
        }
      ]
      
      mountPoints = [
        {
          sourceVolume  = "prometheus-data"
          containerPath = "/prometheus"
        },
        {
          sourceVolume  = "prometheus-config"
          containerPath = "/etc/prometheus"
          readOnly      = true
        }
      ]
      
      command = [
        "--config.file=/etc/prometheus/prometheus.yml",
        "--storage.tsdb.path=/prometheus",
        "--web.console.libraries=/etc/prometheus/console_libraries",
        "--web.console.templates=/etc/prometheus/consoles",
        "--storage.tsdb.retention.time=30d",
        "--web.enable-lifecycle",
        "--web.route-prefix=/prometheus",
        "--web.external-url=http://localhost/prometheus"
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_name}-prometheus"
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# Prometheus ECS service
resource "aws_ecs_service" "prometheus" {
  name             = "${var.project_name}-prometheus"
  platform_version = "1.4.0"
  cluster          = aws_ecs_cluster.main.id
  task_definition  = aws_ecs_task_definition.prometheus.arn
  desired_count    = 1
  launch_type      = "FARGATE"
  
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.monitoring.id]
    assign_public_ip = false
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.prometheus.arn
    container_name   = "prometheus"
    container_port   = 9090
  }
  
  depends_on = [aws_lb_listener_rule.prometheus]
}

############################
# Grafana ECS Service
############################

# Grafana task definition
resource "aws_ecs_task_definition" "grafana" {
  family                   = "${var.project_name}-grafana"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  
  cpu    = "512"
  memory = "1024"
  
  volume {
    name = "grafana-data"
    
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.monitoring.id
      
      transit_encryption = "ENABLED"

      authorization_config {
        access_point_id = aws_efs_access_point.grafana.id
        iam             = "ENABLED"
      }
    }
  }

  volume {
    name = "grafana-config"

    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.monitoring.id
      transit_encryption = "ENABLED"

      authorization_config {
        access_point_id = aws_efs_access_point.grafana.id
        iam             = "ENABLED"
      }
    }
  }
  
  container_definitions = jsonencode([
    {
      name  = "grafana"
      image = "grafana/grafana:latest"
      
      portMappings = [
        {
          containerPort = 3000
          protocol      = "tcp"
        }
      ]
      
      mountPoints = [
        {
          sourceVolume  = "grafana-data"
          containerPath = "/var/lib/grafana"
        },
        {
          sourceVolume  = "grafana-config"
          containerPath = "/etc/grafana/provisioning"
          readOnly      = true
        }
      ]
      
      environment = [
        {
          name  = "GF_SECURITY_ADMIN_PASSWORD"
          value = "admin"
        },
        {
          name  = "GF_SERVER_ROOT_URL"
          value = "%(protocol)s://%(domain)s/grafana/"
        },
        {
          name  = "GF_SERVER_SERVE_FROM_SUB_PATH"
          value = "true"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_name}-grafana"
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# Grafana ECS service
resource "aws_ecs_service" "grafana" {
  name             = "${var.project_name}-grafana"
  platform_version = "1.4.0"
  cluster          = aws_ecs_cluster.main.id
  task_definition  = aws_ecs_task_definition.grafana.arn
  desired_count    = 1
  launch_type      = "FARGATE"
  
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.monitoring.id]
    assign_public_ip = false
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.grafana.arn
    container_name   = "grafana"
    container_port   = 3000
  }
  
  depends_on = [aws_lb_listener_rule.grafana]
}

############################
# ALB Target Groups
############################

# Prometheus target group
resource "aws_lb_target_group" "prometheus" {
  name        = "${var.project_name}-prometheus-tg"
  port        = 9090
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  
  health_check {
    path                = "/prometheus/-/healthy"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

# Grafana target group
resource "aws_lb_target_group" "grafana" {
  name        = "${var.project_name}-grafana-tg"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  
  health_check {
    path                = "/grafana/api/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

############################
# ALB Listener Rules
############################

# Prometheus listener rule
resource "aws_lb_listener_rule" "prometheus" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100
  
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.prometheus.arn
  }
  
  condition {
    path_pattern {
      values = ["/prometheus*"]
    }
  }
}

# Grafana listener rule
resource "aws_lb_listener_rule" "grafana" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 200
  
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.grafana.arn
  }
  
  condition {
    path_pattern {
      values = ["/grafana*"]
    }
  }
}

############################
# CloudWatch Log Groups
############################

resource "aws_cloudwatch_log_group" "prometheus" {
  name              = "/ecs/${var.project_name}-prometheus"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "grafana" {
  name              = "/ecs/${var.project_name}-grafana"
  retention_in_days = 7
}