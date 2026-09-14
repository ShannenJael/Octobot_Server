data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

locals {
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)
  persistent_paths = {
    user        = "/octobot/user"
    logs        = "/octobot/logs"
    backtesting = "/octobot/backtesting"
  }
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.name}-vpc" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-igw" }
}

resource "aws_subnet" "public" {
  for_each = { for index, az in local.availability_zones : az => index }

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.value)
  map_public_ip_on_launch = true

  tags = { Name = "${var.name}-public-${each.key}" }
}

resource "aws_subnet" "private" {
  for_each = { for index, az in local.availability_zones : az => index }

  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, each.value + 10)

  tags = { Name = "${var.name}-private-${each.key}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = { Name = "${var.name}-public" }
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  count  = var.use_nat_gateway ? 1 : 0
  domain = "vpc"

  depends_on = [aws_internet_gateway.this]
  tags       = { Name = "${var.name}-nat" }
}

resource "aws_nat_gateway" "this" {
  count = var.use_nat_gateway ? 1 : 0

  allocation_id = aws_eip.nat[0].id
  subnet_id     = values(aws_subnet.public)[0].id

  depends_on = [aws_internet_gateway.this]
  tags       = { Name = "${var.name}-nat" }
}

resource "aws_route_table" "private" {
  count  = var.use_nat_gateway ? 1 : 0
  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[0].id
  }

  tags = { Name = "${var.name}-private" }
}

resource "aws_route_table_association" "private" {
  for_each = var.use_nat_gateway ? aws_subnet.private : {}

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[0].id
}

resource "aws_security_group" "alb" {
  name_prefix = "${var.name}-alb-"
  description = "Restricted public access to the OctoBot load balancer"
  vpc_id      = aws_vpc.this.id

  dynamic "ingress" {
    for_each = toset(var.allowed_ipv4_cidrs)
    content {
      description = "HTTP from an explicitly trusted network"
      protocol    = "tcp"
      from_port   = 80
      to_port     = 80
      cidr_blocks = [ingress.value]
    }
  }

  dynamic "ingress" {
    for_each = var.certificate_arn == null ? toset([]) : toset(var.allowed_ipv4_cidrs)
    content {
      description = "HTTPS from an explicitly trusted network"
      protocol    = "tcp"
      from_port   = 443
      to_port     = 443
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle { create_before_destroy = true }
  tags = { Name = "${var.name}-alb" }
}

resource "aws_security_group" "task" {
  name_prefix = "${var.name}-task-"
  description = "Only the load balancer can connect to OctoBot"
  vpc_id      = aws_vpc.this.id

  ingress {
    description     = "OctoBot web traffic from the ALB"
    protocol        = "tcp"
    from_port       = 5001
    to_port         = 5001
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle { create_before_destroy = true }
  tags = { Name = "${var.name}-task" }
}

resource "aws_security_group" "efs" {
  name_prefix = "${var.name}-efs-"
  description = "NFS access from the OctoBot task only"
  vpc_id      = aws_vpc.this.id

  ingress {
    description     = "NFS from OctoBot"
    protocol        = "tcp"
    from_port       = 2049
    to_port         = 2049
    security_groups = [aws_security_group.task.id]
  }

  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle { create_before_destroy = true }
  tags = { Name = "${var.name}-efs" }
}

resource "aws_efs_file_system" "this" {
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = { Name = "${var.name}-data" }
}

resource "aws_efs_backup_policy" "this" {
  file_system_id = aws_efs_file_system.this.id

  backup_policy {
    status = "ENABLED"
  }
}

resource "aws_efs_mount_target" "this" {
  for_each = aws_subnet.public

  file_system_id  = aws_efs_file_system.this.id
  subnet_id       = each.value.id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "persistent" {
  for_each = local.persistent_paths

  file_system_id = aws_efs_file_system.this.id

  posix_user {
    uid = 0
    gid = 0
  }

  root_directory {
    path = "/${each.key}"

    creation_info {
      owner_uid   = 0
      owner_gid   = 0
      permissions = "0750"
    }
  }

  tags = { Name = "${var.name}-${each.key}" }
}

resource "aws_iam_role" "execution" {
  name_prefix        = "${var.name}-execution-"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name_prefix        = "${var.name}-task-"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

data "aws_iam_policy_document" "task_efs" {
  statement {
    actions = [
      "elasticfilesystem:ClientMount",
      "elasticfilesystem:ClientWrite",
      "elasticfilesystem:ClientRootAccess"
    ]
    resources = [aws_efs_file_system.this.arn]
  }
}

resource "aws_iam_role_policy" "task_efs" {
  name_prefix = "efs-"
  role        = aws_iam_role.task.id
  policy      = data.aws_iam_policy_document.task_efs.json
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "this" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_lb" "this" {
  name               = var.name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = values(aws_subnet.public)[*].id
  idle_timeout       = 300

  enable_deletion_protection = false
}

resource "aws_lb_target_group" "this" {
  name        = var.name
  port        = 5001
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this.id

  deregistration_delay = 60

  health_check {
    enabled             = true
    path                = "/api/ping"
    matcher             = "200"
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 5
  }

  stickiness {
    enabled         = true
    type            = "lb_cookie"
    cookie_duration = 86400
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  dynamic "default_action" {
    for_each = var.certificate_arn == null ? [1] : []
    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.this.arn
    }
  }

  dynamic "default_action" {
    for_each = var.certificate_arn == null ? [] : [1]
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }
}

resource "aws_lb_listener" "https" {
  count = var.certificate_arn == null ? 0 : 1

  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }

  lifecycle {
    precondition {
      condition     = var.domain_name != null && try(trimspace(var.domain_name) != "", false)
      error_message = "domain_name must be set when certificate_arn is set."
    }
  }
}

resource "aws_ecs_task_definition" "this" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.task_cpu)
  memory                   = tostring(var.task_memory)
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  dynamic "volume" {
    for_each = local.persistent_paths
    content {
      name = volume.key

      efs_volume_configuration {
        file_system_id     = aws_efs_file_system.this.id
        transit_encryption = "ENABLED"

        authorization_config {
          access_point_id = aws_efs_access_point.persistent[volume.key].id
          iam             = "ENABLED"
        }
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "octobot"
    image     = var.container_image
    essential = true
    command   = ["--standalone", "--host", "0.0.0.0", "--port", "5001"]

    environment = [
      { name = "WEB_PORT", value = "5001" },
      { name = "PORT", value = "5001" },
      { name = "OCTOBOT_STANDALONE", value = "true" },
      { name = "MARKET_RADAR_CACHE_SECONDS", value = "120" },
      { name = "MARKET_RADAR_AI_ENABLED", value = "false" },
      { name = "MARKET_RADAR_PAPER_HANDOFF_ENABLED", value = "false" }
    ]

    portMappings = [{
      name          = "http"
      containerPort = 5001
      hostPort      = 5001
      protocol      = "tcp"
      appProtocol   = "http"
    }]

    mountPoints = [for name, path in local.persistent_paths : {
      sourceVolume  = name
      containerPath = path
      readOnly      = false
    }]

    healthCheck = {
      command     = ["CMD-SHELL", "curl -fsS -o /dev/null http://127.0.0.1:5001/api/ping || exit 1"]
      interval    = 30
      timeout     = 10
      retries     = 5
      startPeriod = 300
    }

    linuxParameters = { initProcessEnabled = true }
    stopTimeout     = 120

    ulimits = [{
      name      = "nofile"
      softLimit = 65536
      hardLimit = 65536
    }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.this.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "octobot"
      }
    }
  }])
}

resource "aws_ecs_service" "this" {
  name            = var.name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  # Never overlap two live trading tasks during a deployment.
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  health_check_grace_period_seconds  = 300
  wait_for_steady_state              = true

  network_configuration {
    subnets          = var.use_nat_gateway ? values(aws_subnet.private)[*].id : values(aws_subnet.public)[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = var.use_nat_gateway ? false : true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.this.arn
    container_name   = "octobot"
    container_port   = 5001
  }

  depends_on = [
    aws_lb_listener.http,
    aws_lb_listener.https,
    aws_efs_mount_target.this,
    aws_route_table_association.public,
    aws_route_table_association.private
  ]
}
