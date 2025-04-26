#!/bin/bash

# TikTok Analyzer Deployment Script
# This script deploys the application to AWS

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f "config/.env" ]; then
    echo -e "${YELLOW}Loading environment variables from config/.env${NC}"
    export $(grep -v '^#' config/.env | xargs)
else
    echo -e "${RED}config/.env file not found. Please run setup.sh first.${NC}"
    exit 1
fi

# Check required environment variables
if [ -z "$AWS_REGION" ] || [ -z "$S3_BUCKET" ] || [ -z "$APIFY_API_KEY" ]; then
    echo -e "${RED}Missing required environment variables in config/.env${NC}"
    echo "Please make sure AWS_REGION, S3_BUCKET, and APIFY_API_KEY are set."
    exit 1
fi

# Function to display usage
usage() {
    echo -e "Usage: $0 [OPTIONS]"
    echo -e "Deploy the TikTok Analyzer to AWS"
    echo -e "\nOptions:"
    echo -e "  -t, --terraform    Run Terraform to set up infrastructure"
    echo -e "  -d, --docker       Build and push Docker image"
    echo -e "  -f, --full         Full deployment (infrastructure + Docker)"
    echo -e "  -h, --help         Display this help message"
}

# Parse arguments
if [ "$#" -eq 0 ]; then
    usage
    exit 1
fi

TERRAFORM=false
DOCKER=false
FULL=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        -t|--terraform)
            TERRAFORM=true
            shift 1
            ;;
        -d|--docker)
            DOCKER=true
            shift 1
            ;;
        -f|--full)
            FULL=true
            shift 1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

if [ "$FULL" = true ]; then
    TERRAFORM=true
    DOCKER=true
fi

# Validate AWS configuration
echo -e "\n${YELLOW}Validating AWS configuration...${NC}"
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}AWS credentials are not configured correctly.${NC}"
    echo "Run 'aws configure' to set up your AWS credentials."
    exit 1
fi
echo -e "${GREEN}AWS credentials validated.${NC}"

# Build and push Docker image
if [ "$DOCKER" = true ]; then
    echo -e "\n${YELLOW}Building Docker image...${NC}"
    
    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    # ECR repository name
    ECR_REPO="tiktok-analyzer"
    
    # Create ECR repository if it doesn't exist
    echo -e "\n${YELLOW}Creating/checking ECR repository...${NC}"
    if ! aws ecr describe-repositories --repository-names ${ECR_REPO} &> /dev/null; then
        aws ecr create-repository --repository-name ${ECR_REPO}
        echo -e "${GREEN}ECR repository created: ${ECR_REPO}${NC}"
    else
        echo -e "${GREEN}ECR repository already exists: ${ECR_REPO}${NC}"
    fi
    
    # Log in to ECR
    echo -e "\n${YELLOW}Logging in to ECR...${NC}"
    aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
    
    # Build Docker image
    echo -e "\n${YELLOW}Building Docker image...${NC}"
    docker build -t ${ECR_REPO}:latest .
    
    # Tag image with ECR repository
    echo -e "\n${YELLOW}Tagging Docker image...${NC}"
    docker tag ${ECR_REPO}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest
    
    # Push image to ECR
    echo -e "\n${YELLOW}Pushing Docker image to ECR...${NC}"
    docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest
    
    echo -e "${GREEN}Docker image pushed to ECR: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest${NC}"
fi

# Set up infrastructure with Terraform
if [ "$TERRAFORM" = true ]; then
    echo -e "\n${YELLOW}Setting up infrastructure with Terraform...${NC}"
    
    # Change to Terraform directory
    cd terraform
    
    # Initialize Terraform
    echo -e "\n${YELLOW}Initializing Terraform...${NC}"
    terraform init
    
    # Create terraform.tfvars file
    echo -e "\n${YELLOW}Creating terraform.tfvars...${NC}"
    cat > terraform.tfvars <<EOF
aws_region = "${AWS_REGION}"
environment = "dev"
bucket_name = "${S3_BUCKET}"
key_name = "${EC2_KEY_NAME}"
apify_api_key = "${APIFY_API_KEY}"
ssh_allowed_ips = ["0.0.0.0/0"]  # Change this to your IP for better security
EOF
    
    # Plan Terraform changes
    echo -e "\n${YELLOW}Planning Terraform changes...${NC}"
    terraform plan -out=tfplan
    
    # Apply Terraform changes
    echo -e "\n${YELLOW}Applying Terraform changes...${NC}"
    terraform apply tfplan
    
    # Get outputs
    echo -e "\n${YELLOW}Terraform outputs:${NC}"
    terraform output
    
    # Change back to root directory
    cd ..
    
    echo -e "${GREEN}Infrastructure setup completed.${NC}"
fi

echo -e "\n${GREEN}=== Deployment Complete ===${NC}"