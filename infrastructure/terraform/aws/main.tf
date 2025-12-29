# AWS Infrastructure for Production AI Agent System
#
# This Terraform configuration provisions:
# - EKS cluster for Kubernetes orchestration
# - ElastiCache Redis for state/caching
# - RDS PostgreSQL for persistent data (optional)
# - VPC with public/private subnets
# - Application Load Balancer
# - CloudWatch for logging and monitoring
# - Secrets Manager for API keys
# - IAM roles and policies
#
# Usage:
#   terraform init
#   terraform plan -var-file="production.tfvars"
#   terraform apply -var-file="production.tfvars"

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }

  # Remote state backend (recommended for production)
  backend "s3" {
    bucket         = "your-terraform-state-bucket"
    key            = "agent-system/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}

# Provider configuration
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "production-agents"
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = var.cost_center
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# Local variables
locals {
  cluster_name = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  # Calculate subnet CIDR blocks
  azs = slice(data.aws_availability_zones.available.names, 0, var.availability_zones_count)
}

#############################################
# VPC and Networking
#############################################

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.cluster_name}-vpc"
  cidr = var.vpc_cidr

  azs             = local.azs
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "production" # Cost optimization for non-prod
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Kubernetes tags for subnet discovery
  public_subnet_tags = {
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }

  tags = local.common_tags
}

#############################################
# EKS Cluster
#############################################

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = local.cluster_name
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Cluster endpoint access
  cluster_endpoint_public_access  = var.cluster_endpoint_public_access
  cluster_endpoint_private_access = true

  # Cluster add-ons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = = true
    }
  }

  # EKS managed node groups
  eks_managed_node_groups = {
    # General purpose nodes
    general = {
      name = "${local.cluster_name}-general"

      instance_types = var.node_instance_types
      capacity_type  = var.node_capacity_type # "ON_DEMAND" or "SPOT"

      min_size     = var.node_group_min_size
      max_size     = var.node_group_max_size
      desired_size = var.node_group_desired_size

      # Disk configuration
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            iops                  = 3000
            throughput            = 125
            encrypted             = true
            delete_on_termination = true
          }
        }
      }

      # Labels and taints
      labels = {
        workload = "agent"
      }

      tags = merge(
        local.common_tags,
        {
          Name = "${local.cluster_name}-general-node"
        }
      )
    }

    # Monitoring nodes (optional - for dedicated monitoring stack)
    monitoring = {
      name = "${local.cluster_name}-monitoring"

      instance_types = ["t3.large"]
      capacity_type  = "ON_DEMAND"

      min_size     = 1
      max_size     = 3
      desired_size = 1

      labels = {
        workload = "monitoring"
      }

      taints = [{
        key    = "monitoring"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]

      tags = merge(
        local.common_tags,
        {
          Name = "${local.cluster_name}-monitoring-node"
        }
      )
    }
  }

  # Cluster security group rules
  cluster_security_group_additional_rules = {
    ingress_nodes_ephemeral_ports_tcp = {
      description                = "Nodes on ephemeral ports"
      protocol                   = "tcp"
      from_port                  = 1025
      to_port                    = 65535
      type                       = "ingress"
      source_node_security_group = true
    }
  }

  # Node security group rules
  node_security_group_additional_rules = {
    ingress_self_all = {
      description = "Node to node all ports/protocols"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      type        = "ingress"
      self        = true
    }

    # Allow nodes to communicate with ALB
    ingress_alb_agent = {
      description              = "ALB to agent nodes"
      protocol                 = "tcp"
      from_port                = 8000
      to_port                  = 8000
      type                     = "ingress"
      source_security_group_id = aws_security_group.alb.id
    }
  }

  tags = local.common_tags
}

#############################################
# ElastiCache Redis
#############################################

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.cluster_name}-redis-subnet"
  subnet_ids = module.vpc.private_subnets

  tags = local.common_tags
}

resource "aws_security_group" "redis" {
  name_prefix = "${local.cluster_name}-redis-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for Redis cluster"

  ingress {
    description     = "Redis from EKS nodes"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cluster_name}-redis-sg"
    }
  )
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.cluster_name}-redis"
  replication_group_description = "Redis cluster for agent state and caching"

  engine               = "redis"
  engine_version       = var.redis_engine_version
  node_type            = var.redis_node_type
  num_cache_clusters   = var.redis_num_replicas
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  port                 = 6379

  # Subnet and security
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  # High availability
  automatic_failover_enabled = var.redis_num_replicas > 1
  multi_az_enabled          = var.redis_num_replicas > 1

  # Maintenance
  maintenance_window       = "sun:05:00-sun:06:00"
  snapshot_window          = "03:00-04:00"
  snapshot_retention_limit = var.redis_snapshot_retention_days

  # Encryption
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled        = true
  auth_token                = random_password.redis_auth_token.result

  # Backup
  final_snapshot_identifier = "${local.cluster_name}-redis-final-snapshot"

  # Notifications
  notification_topic_arn = aws_sns_topic.alerts.arn

  tags = local.common_tags
}

resource "aws_elasticache_parameter_group" "redis" {
  name   = "${local.cluster_name}-redis-params"
  family = "redis7"

  # Memory management
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  # Performance tuning
  parameter {
    name  = "timeout"
    value = "300"
  }

  tags = local.common_tags
}

resource "random_password" "redis_auth_token" {
  length  = 32
  special = true
}

#############################################
# Secrets Manager
#############################################

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name_prefix             = "${local.cluster_name}-anthropic-api-key-"
  description             = "Anthropic API key for agent system"
  recovery_window_in_days = var.environment == "production" ? 30 : 0

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "anthropic_api_key" {
  secret_id     = aws_secretsmanager_secret.anthropic_api_key.id
  secret_string = var.anthropic_api_key
}

resource "aws_secretsmanager_secret" "redis_auth_token" {
  name_prefix             = "${local.cluster_name}-redis-token-"
  description             = "Redis authentication token"
  recovery_window_in_days = var.environment == "production" ? 30 : 0

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "redis_auth_token" {
  secret_id     = aws_secretsmanager_secret.redis_auth_token.id
  secret_string = random_password.redis_auth_token.result
}

#############################################
# Application Load Balancer
#############################################

resource "aws_security_group" "alb" {
  name_prefix = "${local.cluster_name}-alb-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for Application Load Balancer"

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP from internet (redirect to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cluster_name}-alb-sg"
    }
  )
}

resource "aws_lb" "main" {
  name               = "${local.cluster_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = var.environment == "production"
  enable_http2              = true
  enable_cross_zone_load_balancing = true

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    enabled = true
  }

  tags = local.common_tags
}

resource "aws_s3_bucket" "alb_logs" {
  bucket_prefix = "${local.cluster_name}-alb-logs-"

  tags = local.common_tags
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "delete-old-logs"
    status = "Enabled"

    expiration {
      days = 90
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
}

#############################################
# CloudWatch Log Groups
#############################################

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/aws/eks/${local.cluster_name}/agent"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}

#############################################
# SNS for Alerts
#############################################

resource "aws_sns_topic" "alerts" {
  name_prefix = "${local.cluster_name}-alerts-"

  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count = var.alert_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

#############################################
# IAM Roles for Service Accounts (IRSA)
#############################################

# IAM role for agent pods
module "agent_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.cluster_name}-agent-role"

  role_policy_arns = {
    secrets_manager = aws_iam_policy.agent_secrets_access.arn
    cloudwatch      = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["production-agents:agent-service-account"]
    }
  }

  tags = local.common_tags
}

resource "aws_iam_policy" "agent_secrets_access" {
  name_prefix = "${local.cluster_name}-agent-secrets-"
  description = "Allow agent to read secrets from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.anthropic_api_key.arn,
          aws_secretsmanager_secret.redis_auth_token.arn
        ]
      }
    ]
  })

  tags = local.common_tags
}

#############################################
# Outputs
#############################################

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_reader_endpoint" {
  description = "Redis reader endpoint (for read replicas)"
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "anthropic_api_key_secret_arn" {
  description = "ARN of the Anthropic API key secret"
  value       = aws_secretsmanager_secret.anthropic_api_key.arn
}

output "redis_auth_token_secret_arn" {
  description = "ARN of the Redis auth token secret"
  value       = aws_secretsmanager_secret.redis_auth_token.arn
}

output "agent_role_arn" {
  description = "ARN of the IAM role for agent service account"
  value       = module.agent_irsa.iam_role_arn
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}
