# AWS deployment

This deployment runs one OctoBot task on Amazon ECS Fargate behind an AWS
Application Load Balancer. Runtime data is stored on encrypted Amazon EFS and
logs are also sent to CloudWatch Logs. It does not use Netlify or Cloudflare.

## Architecture

```text
Trusted browser
      |
      v
Application Load Balancer (HTTP or HTTPS, CIDR restricted)
      |
      v
One ECS Fargate task (OctoBot :5001)
      |
      +---- encrypted EFS: user, tentacles, logs, backtesting
      +---- CloudWatch Logs
      +---- outbound exchange/API connections
```

The service deliberately runs exactly one task. Starting two copies against the
same trading account could duplicate trading actions. Deployments stop the old
task before starting the new one for the same reason.

## Prerequisites

- An AWS account and AWS CLI credentials with permission to create VPC, ECS,
  ELB, EFS, IAM, and CloudWatch resources
- Terraform 1.6 or newer
- A trusted public IPv4 address to allowlist
- Optional: an ACM certificate and DNS name for HTTPS

AWS resources created by this configuration incur charges. The Application Load
Balancer, Fargate task, EFS, logs, and optional NAT gateway are billed separately.
Run `terraform plan` and review the AWS Pricing Calculator before applying.

## Deploy

From `aws/terraform`:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and replace `203.0.113.10/32` with your public address.
Do not use `0.0.0.0/0` for a trading dashboard.

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out octobot.tfplan
terraform apply octobot.tfplan
terraform output -raw application_url
```

The initial health check can take approximately five minutes while OctoBot
initializes. The default image is the official stable image. Before real trading,
replace the floating `stable` tag with a version or immutable image digest that
you have tested.

## HTTPS and DNS

For initial testing, the load balancer can serve HTTP to the restricted CIDR.
Before entering exchange credentials, configure a domain and HTTPS:

1. Request or import an ACM certificate in the same Region as the deployment.
2. Set `certificate_arn` in `terraform.tfvars` and apply again.
3. Point a DNS alias or CNAME at `load_balancer_dns_name` from Terraform output.

When `certificate_arn` is set, port 80 redirects to HTTPS and the load balancer
uses a TLS 1.2/1.3 security policy. The load balancer supports the WebSocket
connections used by OctoBot and has a five-minute idle timeout.

## Network modes

The default, lower-cost mode places the Fargate task in public subnets so it can
reach cryptocurrency exchanges without a NAT gateway. The task receives a public
IP, but its security group accepts inbound traffic only from the load balancer;
the load balancer itself accepts traffic only from `allowed_ipv4_cidrs`.

For stricter network isolation, set:

```hcl
use_nat_gateway = true
```

This places the task in private subnets and sends outbound traffic through one
NAT gateway. A NAT gateway has a meaningful fixed monthly cost and a single NAT
gateway is not multi-AZ resilient.

## Operations

Check service state:

```bash
aws ecs describe-services --region us-east-2 --cluster octobot --services octobot
```

Follow application logs:

```bash
aws logs tail /ecs/octobot --region us-east-2 --follow
```

Restart the task after configuration or secret changes:

```bash
aws ecs update-service --region us-east-2 --cluster octobot --service octobot --force-new-deployment
```

Back up EFS before upgrades and validate new versions in simulated trading mode.
Exchange credentials and the contents of the local `user` directory must never
be committed to Git or placed in Terraform variables/state.

## Migrating existing local state

Do not copy a live data directory while the local bot is writing to it. Stop the
local container, back up `user` and any required backtesting data,
then transfer them to EFS using an encrypted, temporary migration host or AWS
DataSync. Start the AWS task only after the copy completes. Logs normally do not
need to be migrated because AWS sends new container output to CloudWatch.

Tentacles are image-managed in this deployment. This prevents a blank EFS mount
from hiding OctoBot and the Market Radar plug-in baked into the image. Publish a
new tested image when changing tentacles rather than copying them into EFS.

## Removal

First back up any data you need from EFS. Then run `terraform destroy`. Destroying
the stack deletes the EFS file system and its OctoBot state; Terraform will show
the affected resources before asking for confirmation.
