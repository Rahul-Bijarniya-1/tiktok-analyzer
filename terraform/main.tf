provider "aws" {
  region = var.aws_region
}

# S3 bucket for input/output data
resource "aws_s3_bucket" "tiktok_data" {
  bucket = var.bucket_name
  
  tags = {
    Name        = "TikTok Analyzer Data"
    Environment = var.environment
  }
}

# S3 bucket ACL
resource "aws_s3_bucket_ownership_controls" "tiktok_data" {
  bucket = aws_s3_bucket.tiktok_data.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "tiktok_data" {
  depends_on = [aws_s3_bucket_ownership_controls.tiktok_data]
  bucket = aws_s3_bucket.tiktok_data.id
  acl    = "private"
}

# S3 bucket folders
resource "aws_s3_object" "input_folder" {
  bucket = aws_s3_bucket.tiktok_data.id
  key    = "input/"
  content_type = "application/x-directory"
  acl    = "private"
}

resource "aws_s3_object" "output_folder" {
  bucket = aws_s3_bucket.tiktok_data.id
  key    = "output/"
  content_type = "application/x-directory"
  acl    = "private"
}

resource "aws_s3_object" "triggers_folder" {
  bucket = aws_s3_bucket.tiktok_data.id
  key    = "triggers/"
  content_type = "application/x-directory"
  acl    = "private"
}

# SQS Queue for processing tasks
resource "aws_sqs_queue" "tiktok_analyzer_queue" {
  name                      = "tiktok-analyzer-queue"
  delay_seconds             = 0
  max_message_size          = 2048
  message_retention_seconds = 86400  # 1 day
  receive_wait_time_seconds = 10
  visibility_timeout_seconds = 300  # 5 minutes
  
  tags = {
    Name        = "TikTok Analyzer Queue"
    Environment = var.environment
  }
}

# IAM role for EC2 instance
resource "aws_iam_role" "tiktok_analyzer_role" {
  name = "tiktok-analyzer-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Name        = "TikTok Analyzer Role"
    Environment = var.environment
  }
}

# IAM policy for EC2 instance
resource "aws_iam_policy" "tiktok_analyzer_policy" {
  name        = "tiktok-analyzer-policy"
  description = "Policy for TikTok Analyzer EC2 instance"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [
          aws_s3_bucket.tiktok_data.arn,
          "${aws_s3_bucket.tiktok_data.arn}/*"
        ]
      },
      {
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:SendMessage"
        ]
        Effect   = "Allow"
        Resource = aws_sqs_queue.tiktok_analyzer_queue.arn
      },
      {
        Action = [
          "cloudwatch:PutMetricData",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "tiktok_analyzer_attachment" {
  role       = aws_iam_role.tiktok_analyzer_role.name
  policy_arn = aws_iam_policy.tiktok_analyzer_policy.arn
}

# EC2 instance profile
resource "aws_iam_instance_profile" "tiktok_analyzer_profile" {
  name = "tiktok-analyzer-profile"
  role = aws_iam_role.tiktok_analyzer_role.name
}

# Security group for EC2 instance
resource "aws_security_group" "tiktok_analyzer_sg" {
  name        = "tiktok_analyzer_sg"
  description = "Security group for TikTok Analyzer"
  
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_ips
    description = "SSH access"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  
  tags = {
    Name        = "TikTok Analyzer SG"
    Environment = var.environment
  }
}

# EC2 instance with GPU
resource "aws_instance" "tiktok_analyzer" {
  ami                    = var.ami_id
  instance_type          = "t2.micro"  # GPU instance
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.tiktok_analyzer_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.tiktok_analyzer_profile.name
  
  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }
  
  tags = {
    Name        = "TikTok Analyzer"
    Environment = var.environment
  }
  
  user_data = <<-EOF
              #!/bin/bash
              apt-get update
              apt-get install -y docker.io awscli
              systemctl start docker
              systemctl enable docker
              
              # Install NVIDIA Container Toolkit
              distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
              curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
              curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
              apt-get update
              apt-get install -y nvidia-docker2
              systemctl restart docker
              
              # Set up environment variables
              cat > /etc/environment <<EOL
              APIFY_API_KEY=${var.apify_api_key}
              AWS_REGION=${var.aws_region}
              S3_BUCKET=${var.bucket_name}
              SQS_QUEUE_URL=${aws_sqs_queue.tiktok_analyzer_queue.id}
              USE_GPU=True
              BATCH_SIZE=16
              EOL
              
              # Clone repository
              git clone  /opt/tiktok-analyzer
              cd /opt/tiktok-analyzer
              
              # Run docker container
              docker run -d --name tiktok-analyzer \
                --restart unless-stopped \
                --gpus all \
                -e APIFY_API_KEY=${var.apify_api_key} \
                -e AWS_REGION=${var.aws_region} \
                -e S3_BUCKET=${var.bucket_name} \
                -e SQS_QUEUE_URL=${aws_sqs_queue.tiktok_analyzer_queue.id} \
                -e USE_GPU=True \
                -e BATCH_SIZE=16 \
                yourusername/tiktok-analyzer:latest
              EOF
}

# CloudWatch dashboard
resource "aws_cloudwatch_dashboard" "tiktok_analyzer_dashboard" {
  dashboard_name = "TikTokAnalyzer"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.tiktok_analyzer.id]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "CPU Utilization"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["TikTokAnalyzer", "ProcessedUsernames"]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Processed Usernames"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["TikTokAnalyzer", "ErrorCount"]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Error Count"
        }
      }
    ]
  })
}

# CloudWatch alarm for high CPU utilization
resource "aws_cloudwatch_metric_alarm" "high_cpu_alarm" {
  alarm_name          = "high-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "This metric monitors EC2 CPU utilization"
  
  dimensions = {
    InstanceId = aws_instance.tiktok_analyzer.id
  }
}

# CloudWatch alarm for high error rate
resource "aws_cloudwatch_metric_alarm" "high_error_alarm" {
  alarm_name          = "high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ErrorCount"
  namespace           = "TikTokAnalyzer"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "This metric monitors processing errors"
}