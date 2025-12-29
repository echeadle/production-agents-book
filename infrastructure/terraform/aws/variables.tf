# Variables for AWS infrastructure

#############################################
# General
#############################################

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "production-agents"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-west-2"
}

variable "cost_center" {
  description = "Cost center tag for billing"
  type        = string
  default     = "engineering"
}

#############################################
# Networking
#############################################

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones_count" {
  description = "Number of availability zones to use"
  type        = number
  default     = 3

  validation {
    condition     = var.availability_zones_count >= 2 && var.availability_zones_count <= 6
    error_message = "Must use between 2 and 6 availability zones."
  }
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

#############################################
# EKS Cluster
#############################################

variable "kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

variable "cluster_endpoint_public_access" {
  description = "Enable public access to cluster endpoint"
  type        = bool
  default     = true
}

variable "node_instance_types" {
  description = "Instance types for EKS node group"
  type        = list(string)
  default     = ["t3.large"]
}

variable "node_capacity_type" {
  description = "Capacity type for nodes (ON_DEMAND or SPOT)"
  type        = string
  default     = "ON_DEMAND"

  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.node_capacity_type)
    error_message = "Capacity type must be ON_DEMAND or SPOT."
  }
}

variable "node_group_min_size" {
  description = "Minimum number of nodes in node group"
  type        = number
  default     = 3
}

variable "node_group_max_size" {
  description = "Maximum number of nodes in node group"
  type        = number
  default     = 10
}

variable "node_group_desired_size" {
  description = "Desired number of nodes in node group"
  type        = number
  default     = 3
}

#############################################
# ElastiCache Redis
#############################################

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

variable "redis_node_type" {
  description = "Instance type for Redis nodes"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_replicas" {
  description = "Number of Redis read replicas"
  type        = number
  default     = 2

  validation {
    condition     = var.redis_num_replicas >= 1 && var.redis_num_replicas <= 5
    error_message = "Must have between 1 and 5 Redis replicas."
  }
}

variable "redis_snapshot_retention_days" {
  description = "Number of days to retain Redis snapshots"
  type        = number
  default     = 7
}

#############################################
# Secrets
#############################################

variable "anthropic_api_key" {
  description = "Anthropic API key (sensitive)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.anthropic_api_key) > 0
    error_message = "Anthropic API key must be provided."
  }
}

#############################################
# Monitoring and Logging
#############################################

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30

  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch retention period."
  }
}

variable "alert_email" {
  description = "Email address for alerts (optional)"
  type        = string
  default     = ""
}

#############################################
# Tags
#############################################

variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
