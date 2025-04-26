# TikTok Age/Gender Analyzer

A cloud-based system for analyzing TikTok content creators' age and gender using the MiVOLO deep learning model. This project allows large-scale processing of TikTok usernames, extracting thumbnails, and predicting demographic information.

## Features

- Extract thumbnails from TikTok videos based on username
- Analyze images using the MiVOLO model to predict age and gender
- Optimized for GPU processing with batch operations
- Cloud deployment on AWS with auto-scaling capabilities
- Handling of large datasets (10,000+ usernames per month)
- Comprehensive monitoring and error handling

## Architecture Overview

The system is deployed on AWS and consists of:

1. **S3 bucket**: Stores input CSV files, downloaded thumbnails, and output results
2. **SQS queue**: Manages processing jobs
3. **EC2 instances with GPU**: Performs the analysis
4. **CloudWatch**: Provides monitoring and alerting

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (for containerized deployment)
- AWS account with appropriate permissions
- Apify API key for TikTok scraping
- NVIDIA GPU (optional for local development, required for production)

## Quick Start

### Local Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/tiktok-analyzer.git
   cd tiktok-analyzer
   ```

2. Run the setup script:
   ```bash
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

3. Configure environment variables:
   ```bash
   # Edit config/.env with your API keys and settings
   nano config/.env
   ```

4. Create a CSV file with TikTok usernames:
   ```bash
   echo "username" > data/input/usernames.csv
   echo "user1" >> data/input/usernames.csv
   echo "user2" >> data/input/usernames.csv
   ```

5. Run the analyzer:
   ```bash
   python run.py --mode=file --input=data/input/usernames.csv --output=data/output/results.csv
   ```

### Docker Deployment

1. Make sure Docker and Docker Compose are installed.

2. Build and run the Docker container:
   ```bash
   docker-compose up --build
   ```

### AWS Deployment

1. Make sure you have AWS CLI configured:
   ```bash
   aws configure
   ```

2. Run the deployment script:
   ```bash
   chmod +x scripts/deploy.sh
   ./scripts/deploy.sh --full
   ```

## Detailed Installation

### Environment Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install the package in development mode:
   ```bash
   pip install -e .
   ```

### Configuration

1. Copy the template environment file:
   ```bash
   cp config/.env.template config/.env
   ```

2. Edit the environment variables in `config/.env`:
   ```
   # API Keys
   APIFY_API_KEY=your_apify_api_key_here

   # AWS Configuration
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=your_access_key_id
   AWS_SECRET_ACCESS_KEY=your_secret_access_key
   S3_BUCKET=tiktok-analyzer-data
   SQS_QUEUE_URL=https://sqs.region.amazonaws.com/account-id/queue-name

   # GPU Settings
   USE_GPU=True
   BATCH_SIZE=16

   # Scraper Settings
   THUMBNAILS_PER_USER=10
   MAX_RETRIES=3
   RETRY_DELAY=5
   ```

### AWS Infrastructure Setup

1. Initialize Terraform:
   ```bash
   cd terraform
   terraform init
   ```

2. Create the `terraform.tfvars` file:
   ```bash
   cat > terraform.tfvars <<EOF
   aws_region = "us-east-1"
   environment = "dev"
   bucket_name = "tiktok-analyzer-data"
   key_name = "your-key-name"
   apify_api_key = "your-apify-api-key"
   ssh_allowed_ips = ["your.ip.address/32"]
   EOF
   ```

3. Apply the Terraform configuration:
   ```bash
   terraform apply
   ```

4. Note the outputs for future reference:
   ```bash
   terraform output
   ```

## Usage

### Processing a CSV File Locally

```bash
python run.py --mode=file --input=data/input/usernames.csv --output=data/output/results.csv
```

### Processing with Cloud Services

```bash
python run.py --mode=file --cloud --input=data/input/usernames.csv --output=data/output/results.csv
```

### Queue-based Processing in the Cloud

```bash
# First, upload usernames to SQS queue
python -c "
import boto3
import csv

sqs = boto3.client('sqs')
queue_url = 'your-sqs-queue-url'

with open('data/input/usernames.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        username = row['username']
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=username
        )
        print(f'Sent {username} to queue')
"

# Then, run the processor in queue mode
python run.py --mode=queue --cloud
```

## Monitoring and Operations

### CloudWatch Dashboard

A CloudWatch dashboard is automatically created by Terraform, providing metrics such as:
- CPU Utilization
- GPU Utilization
- Processed Usernames
- Error Count

Access the dashboard at:
```
https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=TikTokAnalyzer
```

### Scaling

The system scales automatically based on the SQS queue depth. You can adjust the scaling parameters in the Terraform configuration:

```hcl
# In terraform/main.tf, adjust the auto-scaling parameters
resource "aws_autoscaling_policy" "scale_up" {
  # ...
  adjustment_type = "ChangeInCapacity"
  scaling_adjustment = 1
  cooldown = 300
  # ...
}
```

### Cost Optimization

To optimize costs, you can:
1. Use spot instances for processing
2. Schedule the EC2 instances to shut down during off-hours
3. Adjust the batch size to maximize GPU utilization

## Troubleshooting

### Common Issues

1. **TikTok API rate limiting**:
   - Increase `RETRY_DELAY` in `config/.env`
   - Use multiple Apify API keys with rotation

2. **GPU memory errors**:
   - Reduce `BATCH_SIZE` in `config/.env`
   - Use a larger instance type (e.g., g4dn.2xlarge)

3. **Missing thumbnails**:
   - Check TikTok user privacy settings
   - Verify the Apify API key is valid

### Logs

- CloudWatch Logs: `/aws/ec2/tiktok-analyzer`
- EC2 Instance Logs: `/var/log/cloud-init-output.log`
- Docker Logs: `docker logs tiktok-analyzer`

## Testing

Run the tests with:
```bash
python -m pytest tests/
```

For specific test categories:
```bash
python -m pytest tests/test_scraper.py
python -m pytest tests/test_analyzer.py
python -m pytest tests/test_integration.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [MiVOLO](https://github.com/WildChlamydia/MiVOLO) for the age and gender prediction model
- [YOLOv8](https://github.com/ultralytics/ultralytics) for face and person detection
- [Apify](https://apify.com/) for the TikTok scraping API