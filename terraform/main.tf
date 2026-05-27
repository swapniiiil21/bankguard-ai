terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Enterprise remote state storage
  backend "s3" {
    bucket         = "bankguard-tf-state-prod"
    key            = "eks/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "bankguard-tf-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}

# --- VPC Module ---
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"

  name = "bankguard-vpc-prod"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false
}

# --- EKS Cluster Module ---
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "19.16.0"

  cluster_name    = "bankguard-cluster-prod"
  cluster_version = "1.28"

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    # Node Group A: CPU intensive API Gateway and Kafka
    core_services = {
      min_size     = 3
      max_size     = 10
      desired_size = 3
      instance_types = ["m5.xlarge"]
      labels = {
        workload = "core"
      }
    }
    # Node Group B: GPU intensive vLLM embedding/inference fallback
    gpu_inference = {
      min_size     = 1
      max_size     = 5
      desired_size = 1
      instance_types = ["g5.2xlarge"] # NVIDIA A10G
      labels = {
        workload = "gpu-inference"
      }
      taints = [
        {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }
}
