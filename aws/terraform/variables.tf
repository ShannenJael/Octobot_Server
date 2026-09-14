variable "aws_region" {
  description = "AWS Region in which to deploy OctoBot."
  type        = string
  default     = "us-east-2"
}

variable "name" {
  description = "Prefix used for AWS resource names."
  type        = string
  default     = "octobot"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.name))
    error_message = "name must start with a lowercase letter and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated OctoBot VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "container_image" {
  description = "Container image to run. Pin a version or digest before using real funds."
  type        = string
  default     = "drakkarsoftware/octobot:stable"
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "allowed_ipv4_cidrs" {
  description = "IPv4 networks allowed to reach the dashboard. Keep this restricted to trusted addresses."
  type        = list(string)
  default     = []
}

variable "certificate_arn" {
  description = "Optional ACM certificate ARN. When set, HTTP redirects to HTTPS. The certificate must be in aws_region."
  type        = string
  default     = null
  nullable    = true
}

variable "domain_name" {
  description = "Public DNS name covered by certificate_arn. DNS is managed separately."
  type        = string
  default     = null
  nullable    = true
}

variable "use_nat_gateway" {
  description = "Run the task in private subnets behind a NAT gateway. Safer, but adds a substantial fixed monthly charge."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention period."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags applied to AWS resources."
  type        = map(string)
  default = {
    Environment = "production"
  }
}
