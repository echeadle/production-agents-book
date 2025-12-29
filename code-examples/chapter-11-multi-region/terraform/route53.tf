# Route 53 GeoDNS Configuration for Multi-Region Deployment
# Chapter 11: Multi-Region Deployment
#
# This Terraform configuration sets up geolocation-based DNS routing
# to direct users to their nearest regional deployment.

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# =========================================================================
# Route 53 Hosted Zone
# =========================================================================

resource "aws_route53_zone" "agent" {
  name    = "agent.company.com"
  comment = "Multi-region agent API DNS zone"

  tags = {
    Name        = "agent-api-zone"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = "AI-Agent-Production"
  }
}

# =========================================================================
# Regional Load Balancers (Data Sources)
# =========================================================================

# US-East Load Balancer
data "aws_lb" "us_east" {
  provider = aws.us_east_1
  name     = "agent-alb-us-east"
}

# EU-West Load Balancer
data "aws_lb" "eu_west" {
  provider = aws.eu_west_1
  name     = "agent-alb-eu-west"
}

# AP-Southeast Load Balancer
data "aws_lb" "ap_southeast" {
  provider = aws.ap_southeast_1
  name     = "agent-alb-ap-southeast"
}

# =========================================================================
# Health Checks for Regional Endpoints
# =========================================================================

# US-East Health Check
resource "aws_route53_health_check" "us_east" {
  fqdn              = data.aws_lb.us_east.dns_name
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30  # Check every 30 seconds

  # Enable latency measurement
  measure_latency = true

  # Enable SNI (required for HTTPS health checks with ALB)
  enable_sni = true

  tags = {
    Name   = "agent-health-us-east"
    Region = "us-east-1"
  }
}

# EU-West Health Check
resource "aws_route53_health_check" "eu_west" {
  fqdn              = data.aws_lb.eu_west.dns_name
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  measure_latency = true
  enable_sni      = true

  tags = {
    Name   = "agent-health-eu-west"
    Region = "eu-west-1"
  }
}

# AP-Southeast Health Check
resource "aws_route53_health_check" "ap_southeast" {
  fqdn              = data.aws_lb.ap_southeast.dns_name
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  measure_latency = true
  enable_sni      = true

  tags = {
    Name   = "agent-health-ap-southeast"
    Region = "ap-southeast-1"
  }
}

# =========================================================================
# CloudWatch Alarms for Health Checks
# =========================================================================

resource "aws_cloudwatch_metric_alarm" "us_east_health" {
  alarm_name          = "route53-health-us-east-failed"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  alarm_description   = "US-East health check failing"
  treat_missing_data  = "breaching"

  dimensions = {
    HealthCheckId = aws_route53_health_check.us_east.id
  }

  alarm_actions = [var.pagerduty_sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "eu_west_health" {
  alarm_name          = "route53-health-eu-west-failed"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  alarm_description   = "EU-West health check failing"
  treat_missing_data  = "breaching"

  dimensions = {
    HealthCheckId = aws_route53_health_check.eu_west.id
  }

  alarm_actions = [var.pagerduty_sns_topic_arn]
}

# =========================================================================
# Geolocation DNS Records
# =========================================================================

# North America → US-East
resource "aws_route53_record" "north_america" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "NA"  # North America
  }

  # Evaluate target health before routing
  set_identifier  = "north-america"
  health_check_id = aws_route53_health_check.us_east.id

  alias {
    name                   = data.aws_lb.us_east.dns_name
    zone_id                = data.aws_lb.us_east.zone_id
    evaluate_target_health = true
  }
}

# South America → US-East (geographically closer)
resource "aws_route53_record" "south_america" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "SA"  # South America
  }

  set_identifier  = "south-america"
  health_check_id = aws_route53_health_check.us_east.id

  alias {
    name                   = data.aws_lb.us_east.dns_name
    zone_id                = data.aws_lb.us_east.zone_id
    evaluate_target_health = true
  }
}

# Europe → EU-West
resource "aws_route53_record" "europe" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "EU"  # Europe
  }

  set_identifier  = "europe"
  health_check_id = aws_route53_health_check.eu_west.id

  alias {
    name                   = data.aws_lb.eu_west.dns_name
    zone_id                = data.aws_lb.eu_west.zone_id
    evaluate_target_health = true
  }
}

# Africa → EU-West (geographically closer)
resource "aws_route53_record" "africa" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "AF"  # Africa
  }

  set_identifier  = "africa"
  health_check_id = aws_route53_health_check.eu_west.id

  alias {
    name                   = data.aws_lb.eu_west.dns_name
    zone_id                = data.aws_lb.eu_west.zone_id
    evaluate_target_health = true
  }
}

# Asia → AP-Southeast
resource "aws_route53_record" "asia" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "AS"  # Asia
  }

  set_identifier  = "asia"
  health_check_id = aws_route53_health_check.ap_southeast.id

  alias {
    name                   = data.aws_lb.ap_southeast.dns_name
    zone_id                = data.aws_lb.ap_southeast.zone_id
    evaluate_target_health = true
  }
}

# Oceania (Australia, New Zealand) → AP-Southeast
resource "aws_route53_record" "oceania" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "OC"  # Oceania
  }

  set_identifier  = "oceania"
  health_check_id = aws_route53_health_check.ap_southeast.id

  alias {
    name                   = data.aws_lb.ap_southeast.dns_name
    zone_id                = data.aws_lb.ap_southeast.zone_id
    evaluate_target_health = true
  }
}

# Default fallback → US-East
# This catches any requests that don't match the above rules
resource "aws_route53_record" "default" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    location = "*"  # Default (catch-all)
  }

  set_identifier  = "default"
  health_check_id = aws_route53_health_check.us_east.id

  alias {
    name                   = data.aws_lb.us_east.dns_name
    zone_id                = data.aws_lb.us_east.zone_id
    evaluate_target_health = true
  }
}

# =========================================================================
# Regional-Specific DNS Records (for explicit routing)
# =========================================================================

# api-us.agent.company.com → US-East (always)
resource "aws_route53_record" "us_explicit" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api-us.agent.company.com"
  type    = "A"

  alias {
    name                   = data.aws_lb.us_east.dns_name
    zone_id                = data.aws_lb.us_east.zone_id
    evaluate_target_health = true
  }
}

# api-eu.agent.company.com → EU-West (always)
resource "aws_route53_record" "eu_explicit" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api-eu.agent.company.com"
  type    = "A"

  alias {
    name                   = data.aws_lb.eu_west.dns_name
    zone_id                = data.aws_lb.eu_west.zone_id
    evaluate_target_health = true
  }
}

# api-ap.agent.company.com → AP-Southeast (always)
resource "aws_route53_record" "ap_explicit" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api-ap.agent.company.com"
  type    = "A"

  alias {
    name                   = data.aws_lb.ap_southeast.dns_name
    zone_id                = data.aws_lb.ap_southeast.zone_id
    evaluate_target_health = true
  }
}

# =========================================================================
# Failover Configuration (Primary/Secondary)
# =========================================================================

# Primary record (weighted 100% when healthy)
resource "aws_route53_record" "failover_primary" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api-failover.agent.company.com"
  type    = "A"

  failover_routing_policy {
    type = "PRIMARY"
  }

  set_identifier  = "primary"
  health_check_id = aws_route53_health_check.us_east.id

  alias {
    name                   = data.aws_lb.us_east.dns_name
    zone_id                = data.aws_lb.us_east.zone_id
    evaluate_target_health = true
  }
}

# Failover record (used only if primary fails)
resource "aws_route53_record" "failover_secondary" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api-failover.agent.company.com"
  type    = "A"

  failover_routing_policy {
    type = "SECONDARY"
  }

  set_identifier  = "secondary"
  health_check_id = aws_route53_health_check.eu_west.id

  alias {
    name                   = data.aws_lb.eu_west.dns_name
    zone_id                = data.aws_lb.eu_west.zone_id
    evaluate_target_health = true
  }
}

# =========================================================================
# Outputs
# =========================================================================

output "zone_id" {
  description = "Route 53 hosted zone ID"
  value       = aws_route53_zone.agent.zone_id
}

output "name_servers" {
  description = "Name servers for the hosted zone (update domain registrar)"
  value       = aws_route53_zone.agent.name_servers
}

output "api_endpoint" {
  description = "Main API endpoint (geo-routed)"
  value       = "https://api.agent.company.com"
}

output "health_check_ids" {
  description = "Health check IDs for monitoring"
  value = {
    us_east      = aws_route53_health_check.us_east.id
    eu_west      = aws_route53_health_check.eu_west.id
    ap_southeast = aws_route53_health_check.ap_southeast.id
  }
}

# =========================================================================
# Variables
# =========================================================================

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "pagerduty_sns_topic_arn" {
  description = "SNS topic ARN for PagerDuty alerts"
  type        = string
}

# =========================================================================
# Provider Configuration
# =========================================================================

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

provider "aws" {
  alias  = "eu_west_1"
  region = "eu-west-1"
}

provider "aws" {
  alias  = "ap_southeast_1"
  region = "ap-southeast-1"
}

# =========================================================================
# Usage Instructions
# =========================================================================

# 1. Initialize Terraform:
#    terraform init
#
# 2. Plan the deployment:
#    terraform plan -var="pagerduty_sns_topic_arn=arn:aws:sns:us-east-1:123456789:pagerduty"
#
# 3. Apply the configuration:
#    terraform apply
#
# 4. Update domain registrar with the name servers output
#
# 5. Test DNS resolution:
#    dig api.agent.company.com
#    dig api-us.agent.company.com
#
# 6. Test geolocation routing:
#    curl -H "Host: api.agent.company.com" https://api.agent.company.com/health
#
# 7. Monitor health checks in CloudWatch
