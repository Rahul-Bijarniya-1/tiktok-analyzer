#!/bin/bash

# TikTok Analyzer Test Script
# This script runs various tests for the TikTok Analyzer

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

# Function to display usage
usage() {
    echo -e "Usage: $0 [OPTIONS]"
    echo -e "Run tests for the TikTok Analyzer"
    echo -e "\nOptions:"
    echo -e "  -l, --local        Run local unit tests"
    echo -e "  -d, --docker       Test Docker container"
    echo -e "  -c, --cloud        Test cloud deployment"
    echo -e "  -a, --all          Run all tests"
    echo -e "  -h, --help         Display this help message"
}

# Parse arguments
if [ "$#" -eq 0 ]; then
    usage
    exit 1
fi

LOCAL=false
DOCKER=false
CLOUD=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        -l|--local)
            LOCAL=true
            shift 1
            ;;
        -d|--docker)
            DOCKER=true
            shift 1
            ;;
        -c|--cloud)
            CLOUD=true
            shift 1
            ;;
        -a|--all)
            LOCAL=true
            DOCKER=true
            CLOUD=true
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

# Create test data if it doesn't exist
echo -e "\n${YELLOW}Creating test data...${NC}"
mkdir -p data/input
if [ ! -f "data/input/test_usernames.csv" ]; then
    echo "username" > data/input/test_usernames.csv
    echo "user1" >> data/input/test_usernames.csv
    echo "user2" >> data/input/test_usernames.csv
    echo -e "${GREEN}Created test data: data/input/test_usernames.csv${NC}"
else
    echo -e "${GREEN}Test data already exists: data/input/test_usernames.csv${NC}"
fi

# Run local unit tests
if [ "$LOCAL" = true ]; then
    echo -e "\n${YELLOW}Running local unit tests...${NC}"
    
    # Activate virtual environment if not already activated
    if [ -z "$VIRTUAL_ENV" ]; then
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
            source venv/Scripts/activate
        else
            source venv/bin/activate
        fi
        echo -e "${GREEN}Virtual environment activated.${NC}"
    fi
    
    # Run pytest
    python -m pytest tests/ -v
    
    # Test environment setup
    echo -e "\n${YELLOW}Testing environment setup...${NC}"
    python tests/test_environment.py
    
    # Test basic functionality
    echo -e "\n${YELLOW}Testing basic functionality...${NC}"
    python run.py --mode=file --input=data/input/test_usernames.csv --output=data/output/test_results.csv
    
    echo -e "\n${GREEN}Local tests completed.${NC}"
fi

# Test Docker container
if [ "$DOCKER" = true ]; then
    echo -e "\n${YELLOW}Testing Docker container...${NC}"
    
    # Build Docker image
    echo -e "\n${YELLOW}Building Docker image...${NC}"
    docker build -t tiktok-analyzer:test .
    
    # Check if NVIDIA Docker is available
    if command -v nvidia-smi &> /dev/null && docker info | grep -q "Runtimes:.*nvidia"; then
        DOCKER_GPU_FLAG="--gpus all"
        echo -e "${GREEN}NVIDIA Docker available, using GPU.${NC}"
    else
        DOCKER_GPU_FLAG=""
        echo -e "${YELLOW}NVIDIA Docker not available, using CPU.${NC}"
    fi
    
    # Run Docker container with test data
    echo -e "\n${YELLOW}Running Docker container with test data...${NC}"
    docker run --rm $DOCKER_GPU_FLAG \
        -v $(pwd)/data:/app/data \
        -e APIFY_API_KEY=${APIFY_API_KEY} \
        tiktok-analyzer:test \
        python run.py --mode=file --input=data/input/test_usernames.csv --output=data/output/docker_test_results.csv
    
    echo -e "\n${GREEN}Docker tests completed.${NC}"
fi

# Test cloud deployment
if [ "$CLOUD" = true ]; then
    echo -e "\n${YELLOW}Testing cloud deployment...${NC}"
    
    # Check AWS configuration
    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}AWS credentials are not configured correctly.${NC}"
        echo "Run 'aws configure' to set up your AWS credentials."
        exit 1
    fi
    
    # Get instance ID
    INSTANCE_ID=$(cd terraform && terraform output -raw ec2_instance_id 2>/dev/null || echo "")
    
    if [ -z "$INSTANCE_ID" ]; then
        echo -e "${RED}EC2 instance ID not found. Make sure you've deployed the infrastructure.${NC}"
        exit 1
    fi
    
    # Get instance public IP
    INSTANCE_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].PublicIpAddress" --output text)
    
    if [ -z "$INSTANCE_IP" ] || [ "$INSTANCE_IP" == "None" ]; then
        echo -e "${RED}EC2 instance public IP not found.${NC}"
        exit 1
    fi
    
    # Upload test data to S3
    echo -e "\n${YELLOW}Uploading test data to S3...${NC}"
    aws s3 cp data/input/test_usernames.csv s3://${S3_BUCKET}/input/test_usernames.csv
    
    # Test SSH connection
    echo -e "\n${YELLOW}Testing SSH connection to EC2 instance...${NC}"
    if [ -z "$EC2_KEY_PATH" ]; then
        echo -e "${YELLOW}EC2_KEY_PATH not set. Enter the path to your EC2 key file:${NC}"
        read EC2_KEY_PATH
    fi
    
    ssh -i "$EC2_KEY_PATH" -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@$INSTANCE_IP echo "SSH connection successful" || {
        echo -e "${RED}SSH connection failed.${NC}"
        exit 1
    }
    
    # Test Docker on EC2
    echo -e "\n${YELLOW}Testing Docker on EC2 instance...${NC}"
    ssh -i "$EC2_KEY_PATH" ubuntu@$INSTANCE_IP "docker ps" || {
        echo -e "${RED}Docker not running on EC2 instance.${NC}"
        exit 1
    }
    
    # Test GPU on EC2
    echo -e "\n${YELLOW}Testing GPU on EC2 instance...${NC}"
    ssh -i "$EC2_KEY_PATH" ubuntu@$INSTANCE_IP "nvidia-smi" || {
        echo -e "${RED}NVIDIA driver not installed or GPU not available on EC2 instance.${NC}"
        exit 1
    }
    
    # Run test on EC2
    echo -e "\n${YELLOW}Running test on EC2 instance...${NC}"
    ssh -i "$EC2_KEY_PATH" ubuntu@$INSTANCE_IP "cd /opt/tiktok-analyzer && docker run --rm --gpus all -e AWS_REGION=${AWS_REGION} -e S3_BUCKET=${S3_BUCKET} -e APIFY_API_KEY=${APIFY_API_KEY} tiktok-analyzer:latest python run.py --mode=file --cloud --input=data/input/test_usernames.csv --output=data/output/cloud_test_results.csv"
    
    # Check result in S3
    echo -e "\n${YELLOW}Checking result in S3...${NC}"
    aws s3 ls s3://${S3_BUCKET}/output/cloud_test_results.csv || {
        echo -e "${RED}Result not found in S3.${NC}"
        exit 1
    }
    
    # Download result from S3
    echo -e "\n${YELLOW}Downloading result from S3...${NC}"
    aws s3 cp s3://${S3_BUCKET}/output/cloud_test_results.csv data/output/cloud_test_results.csv
    
    echo -e "\n${GREEN}Cloud tests completed.${NC}"
fi

echo -e "\n${GREEN}=== All Tests Completed ===${NC}"