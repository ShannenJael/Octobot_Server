output "application_url" {
  description = "OctoBot endpoint. Restrict access and configure HTTPS before entering exchange credentials."
  value       = var.certificate_arn == null ? "http://${aws_lb.this.dns_name}" : "https://${var.domain_name}"
}

output "load_balancer_dns_name" {
  description = "Create a DNS alias/CNAME for this value when using a custom domain."
  value       = aws_lb.this.dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_name" {
  value = aws_ecs_service.this.name
}

output "efs_file_system_id" {
  description = "Persistent OctoBot data file system."
  value       = aws_efs_file_system.this.id
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.this.name
}
