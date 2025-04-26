variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Environment name (e.g. dev, prod)"
  type        = string
  default     = "dev"
}

variable "bucket_name" {
  description = "Name of the S3 bucket for TikTok Analyzer data"
  type        = string
  default     = "tiktok-analyzer-data"
}

variable "ami_id" {
  description = "AMI ID for EC2 instance (Deep Learning AMI with GPU support)"
  type        = string
  default     = "ami-0f1dcc636b69a6438"  # Ubuntu 20.04 Deep Learning AMI
}

variable "key_name" {
  description = "Name of the SSH key pair for EC2 instance"
  type        = string
}

variable "ssh_allowed_ips" {
  description = "List of IP addresses allowed to SSH to the EC2 instance"
  type        = list(string)
  default     = ["0.0.0.0/0"]  # Allow from anywhere (not recommended for production)
}

variable "apify_api_key" {
  description = "Apify API key for TikTok scraping"
  type        = string
  sensitive   = true
}