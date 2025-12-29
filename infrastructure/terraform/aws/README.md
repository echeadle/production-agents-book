# AWS Infrastructure with Terraform

Production-grade AWS infrastructure for AI agent systems using Terraform.

## What Gets Created

This Terraform configuration provisions a complete production environment:

### Core Infrastructure
- **VPC** with public and private subnets across multiple AZs
- **NAT Gateways** for private subnet internet access
- **Internet Gateway** for public subnet access

### Kubernetes (EKS)
- **EKS Cluster** (managed Kubernetes control plane)
- **EKS Node Groups**:
  - General purpose nodes (for agents)
  - Monitoring nodes (for Prometheus/Grafana)
- **EBS CSI Driver** for persistent volumes
- **IAM Roles for Service Accounts** (IRSA)

### Data & Caching
- **ElastiCache Redis** cluster with read replicas
- Multi-AZ for high availability
- Automatic failover
- Encrypted at rest and in transit

### Security
- **AWS Secrets Manager** for API keys
- **Security Groups** with least-privilege rules
- **IAM Roles** with minimal permissions
- **Encryption** at rest and in transit

### Networking
- **Application Load Balancer** (ALB)
- **SSL/TLS termination** (requires ACM certificate)
- **Access logs** to S3

### Monitoring
- **CloudWatch Log Groups** for application logs
- **SNS Topics** for alerts
- **ALB access logs** to S3

## Prerequisites

### Required Tools
- [Terraform](https://www.terraform.io/downloads) >= 1.6
- [AWS CLI](https://aws.amazon.com/cli/) >= 2.0
- [kubectl](https://kubernetes.io/docs/tasks/tools/) >= 1.28
- An AWS account with appropriate permissions

### AWS Permissions Required
Your AWS IAM user/role needs permissions to create:
- VPC, Subnets, NAT Gateways, Internet Gateways
- EKS clusters and node groups
- ElastiCache clusters
- Secrets Manager secrets
- IAM roles and policies
- Security Groups
- Application Load Balancers
- S3 buckets
- CloudWatch log groups
- SNS topics

See `iam-policy.json` for a complete policy.

## Quick Start

### 1. Configure AWS Credentials

```bash
# Configure AWS CLI
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-west-2"

# Verify credentials
aws sts get-caller-identity
```

### 2. Create S3 Backend (First Time Only)

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://your-terraform-state-bucket --region us-west-2

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket your-terraform-state-bucket \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket your-terraform-state-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-west-2
```

### 3. Configure Terraform Backend

Edit `main.tf` and update the backend configuration:

```hcl
terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"  # Change this
    key            = "agent-system/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

### 4. Create Configuration File

```bash
# For development
cp dev.tfvars.example dev.tfvars

# For production
cp production.tfvars.example production.tfvars

# Edit the file and add your values
nano dev.tfvars
```

**IMPORTANT:** Add `*.tfvars` to `.gitignore` - never commit secrets!

### 5. Initialize Terraform

```bash
terraform init
```

### 6. Plan and Apply

```bash
# Review what will be created
terraform plan -var-file="dev.tfvars"

# Create the infrastructure
terraform apply -var-file="dev.tfvars"

# Confirm with 'yes' when prompted
```

This will take **15-20 minutes** to complete.

### 7. Configure kubectl

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --region us-west-2 \
  --name production-agents-dev

# Verify connection
kubectl get nodes
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  AWS Account                                                │
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  VPC (10.0.0.0/16)                                 │   │
│  │                                                    │   │
│  │  ┌──────────────────┐  ┌──────────────────┐      │   │
│  │  │  Public Subnets  │  │  Private Subnets │      │   │
│  │  │                  │  │                  │      │   │
│  │  │  ┌────────────┐  │  │  ┌────────────┐ │      │   │
│  │  │  │    ALB     │  │  │  │  EKS Nodes │ │      │   │
│  │  │  └────────────┘  │  │  │            │ │      │   │
│  │  │        │         │  │  │  Agent Pods│ │      │   │
│  │  │  ┌────────────┐  │  │  └────────────┘ │      │   │
│  │  │  │  NAT GW    │──┼──┼──┐              │      │   │
│  │  │  └────────────┘  │  │  │              │      │   │
│  │  │        │         │  │  │              │      │   │
│  │  │  ┌────────────┐  │  │  │  ┌────────────┐    │   │
│  │  │  │   IGW      │  │  │  │  │   Redis    │    │   │
│  │  │  └────────────┘  │  │  │  │  Cluster   │    │   │
│  │  └──────────────────┘  │  │  └────────────┘    │   │
│  │                        │  │                    │   │
│  └────────────────────────────────────────────────┘   │
│                                                        │
│  ┌────────────────────────────────────────────────┐   │
│  │  Secrets Manager                               │   │
│  │  - Anthropic API Key                           │   │
│  │  - Redis Auth Token                            │   │
│  └────────────────────────────────────────────────┘   │
│                                                        │
│  ┌────────────────────────────────────────────────┐   │
│  │  CloudWatch                                    │   │
│  │  - Application Logs                            │   │
│  │  - Cluster Logs                                │   │
│  └────────────────────────────────────────────────┘   │
│                                                        │
└─────────────────────────────────────────────────────────┘
```

## Cost Estimation

### Development Environment
- **EKS Cluster**: ~$73/month (control plane)
- **EC2 Nodes** (2x t3.medium Spot): ~$30/month
- **Redis** (cache.t3.medium, 1 replica): ~$50/month
- **NAT Gateway**: ~$32/month
- **ALB**: ~$22/month
- **Data transfer, storage**: ~$20/month

**Total: ~$227/month**

### Production Environment
- **EKS Cluster**: ~$73/month
- **EC2 Nodes** (5x t3.xlarge On-Demand): ~$750/month
- **Redis** (cache.r6g.large, 3 replicas): ~$450/month
- **NAT Gateways** (3x multi-AZ): ~$96/month
- **ALB**: ~$22/month
- **Data transfer, storage, logs**: ~$100/month

**Total: ~$1,491/month**

**Plus:** Actual usage costs (API calls, data transfer, CloudWatch logs)

## Outputs

After applying, Terraform will output:

```bash
# View outputs
terraform output

# Get specific output
terraform output cluster_name
terraform output redis_endpoint
```

### Key Outputs
- `cluster_name` - EKS cluster name for kubectl
- `cluster_endpoint` - EKS API endpoint
- `redis_endpoint` - Redis primary endpoint
- `redis_reader_endpoint` - Redis read replica endpoint
- `alb_dns_name` - Load balancer DNS name
- `agent_role_arn` - IAM role ARN for agent pods
- `anthropic_api_key_secret_arn` - Secrets Manager ARN
- `redis_auth_token_secret_arn` - Redis token ARN

## Deploying the Agent

Once infrastructure is ready:

```bash
# Update Kubernetes manifests with Terraform outputs
export REDIS_ENDPOINT=$(terraform output -raw redis_endpoint)
export SECRET_ARN=$(terraform output -raw anthropic_api_key_secret_arn)

# Deploy agent (see ../kubernetes/README.md)
cd ../../kubernetes
kubectl apply -k .
```

## Updating Infrastructure

```bash
# Update variables in tfvars file
nano dev.tfvars

# Plan changes
terraform plan -var-file="dev.tfvars"

# Apply changes
terraform apply -var-file="dev.tfvars"
```

## Destroying Infrastructure

```bash
# WARNING: This deletes everything!
terraform destroy -var-file="dev.tfvars"

# Confirm with 'yes' when prompted
```

**Note:** Some resources have deletion protection:
- Production ALB has deletion protection
- Secrets have 30-day recovery window
- Final Redis snapshot is created

## Security Best Practices

### Secrets Management

1. **Never commit secrets to git**
   ```bash
   # Add to .gitignore
   echo "*.tfvars" >> .gitignore
   echo "terraform.tfstate*" >> .gitignore
   ```

2. **Use environment variables for CI/CD**
   ```bash
   export TF_VAR_anthropic_api_key="your-key"
   terraform apply -var-file="production.tfvars"
   ```

3. **Rotate secrets regularly**
   - Update in Secrets Manager
   - Restart affected pods

### Network Security

- Private subnets for all compute (EKS, Redis)
- Security groups with minimal rules
- No direct internet access to nodes (via NAT)
- ALB for controlled ingress

### IAM Security

- IRSA (IAM Roles for Service Accounts) instead of node IAM roles
- Minimal permissions per service
- No long-lived credentials in containers

## Troubleshooting

### Terraform Errors

```bash
# State is locked
terraform force-unlock <LOCK_ID>

# Resource already exists
terraform import aws_vpc.main vpc-xxxxx

# Clean up and retry
terraform destroy -auto-approve
terraform apply -var-file="dev.tfvars"
```

### EKS Connection Issues

```bash
# Update kubeconfig
aws eks update-kubeconfig --region us-west-2 --name production-agents-dev

# Check IAM permissions
aws eks describe-cluster --name production-agents-dev

# Verify node groups
aws eks list-nodegroups --cluster-name production-agents-dev
```

### Redis Connection Issues

```bash
# Test from EC2 instance in same VPC
redis-cli -h <redis-endpoint> -p 6379 --tls --askpass

# Check security groups
aws ec2 describe-security-groups --group-ids sg-xxxxx
```

## Advanced Configuration

### Using Spot Instances

For cost savings in non-production:

```hcl
node_capacity_type = "SPOT"
node_instance_types = ["t3.large", "t3a.large", "t2.large"]
```

### Multi-Region Setup

See `../../docs/multi-region.md` for guidance on:
- Cross-region VPC peering
- Global Redis (Global Datastore)
- Route 53 for DNS failover
- Cross-region replication

### Custom Node Groups

Add specialized node groups:

```hcl
gpu_nodes = {
  instance_types = ["g4dn.xlarge"]
  ami_type       = "AL2_x86_64_GPU"

  labels = {
    workload = "ml"
  }

  taints = [{
    key    = "nvidia.com/gpu"
    value  = "true"
    effect = "NO_SCHEDULE"
  }]
}
```

## Maintenance

### Regular Tasks

1. **Update Kubernetes version** (every 3-6 months)
   ```bash
   # Update cluster
   terraform apply -var kubernetes_version="1.29"

   # Update node groups (rolling update)
   ```

2. **Update Redis version** (as needed)
   ```bash
   terraform apply -var redis_engine_version="7.2"
   ```

3. **Review and optimize costs**
   - Use AWS Cost Explorer
   - Check for unused resources
   - Consider Reserved Instances for production

4. **Review security groups** (monthly)
   - Remove unused rules
   - Tighten CIDR ranges

5. **Backup verification** (monthly)
   - Test Redis snapshot restore
   - Verify Secrets Manager backups

## Next Steps

- Deploy the agent application (see `../../kubernetes/README.md`)
- Set up monitoring (see `../../monitoring/README.md`)
- Configure CI/CD (see `../../.github/workflows/`)
- Set up log aggregation (Loki, CloudWatch Insights)
- Configure alerts (CloudWatch Alarms, SNS)

## Additional Resources

- [AWS EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [ElastiCache for Redis](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)

## Support

For issues:
- Check Terraform state: `terraform show`
- Review CloudWatch logs
- Check AWS Console for resource status
- Consult the troubleshooting section above
