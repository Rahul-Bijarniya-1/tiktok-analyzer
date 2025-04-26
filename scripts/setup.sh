#!/bin/bash

# TikTok Analyzer Setup Script
# This script sets up the local development environment

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== TikTok Analyzer Setup ===${NC}"
echo "This script will set up the development environment for TikTok Analyzer"

# Check if Python 3.11+ is installed
echo -e "\n${YELLOW}Checking Python version...${NC}"
python_version=$(python --version 2>&1 | awk '{print $2}')
python_major=$(echo $python_version | cut -d. -f1)
python_minor=$(echo $python_version | cut -d. -f2)

if [ "$python_major" -lt 3 ] || ([ "$python_major" -eq 3 ] && [ "$python_minor" -lt 9 ]); then
    echo -e "${RED}Python 3.11 or higher is required. Found Python $python_version${NC}"
    echo "Please install Python 3.11 or higher and try again."
    exit 1
fi

echo -e "${GREEN}Python $python_version found.${NC}"

# Create virtual environment
echo -e "\n${YELLOW}Setting up virtual environment...${NC}"
if [ -d "venv" ]; then
    echo "Virtual environment already exists."
else
    python -m venv venv
    echo -e "${GREEN}Virtual environment created.${NC}"
fi

# Activate virtual environment
echo -e "\n${YELLOW}Activating virtual environment...${NC}"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi
echo -e "${GREEN}Virtual environment activated.${NC}"

# Install dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}Dependencies installed.${NC}"

# Create necessary directories
echo -e "\n${YELLOW}Creating necessary directories...${NC}"
mkdir -p data/input data/output models
echo -e "${GREEN}Directories created.${NC}"

# Create .env file from template if it doesn't exist
echo -e "\n${YELLOW}Setting up environment variables...${NC}"
if [ ! -f "config/.env" ]; then
    cp config/.env.template config/.env
    echo -e "${GREEN}Created config/.env file from template.${NC}"
    echo -e "${YELLOW}Please edit config/.env to add your API keys and configuration.${NC}"
else
    echo "config/.env file already exists."
fi

# Check if Docker is installed
echo -e "\n${YELLOW}Checking Docker installation...${NC}"
if command -v docker &> /dev/null; then
    docker_version=$(docker --version)
    echo -e "${GREEN}Docker is installed: $docker_version${NC}"
else
    echo -e "${YELLOW}Docker is not installed. It is recommended for containerized deployment.${NC}"
    echo "See https://docs.docker.com/get-docker/ for installation instructions."
fi

# Check if NVIDIA Docker is installed (for GPU support)
echo -e "\n${YELLOW}Checking NVIDIA Docker...${NC}"
if command -v nvidia-smi &> /dev/null && command -v docker &> /dev/null; then
    if docker info | grep -q "Runtimes:.*nvidia"; then
        echo -e "${GREEN}NVIDIA Docker runtime is installed.${NC}"
    else
        echo -e "${YELLOW}NVIDIA Docker runtime is not installed.${NC}"
        echo "See https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html for installation instructions."
    fi
else
    echo -e "${YELLOW}NVIDIA Docker components not found. This is OK if you don't have a GPU.${NC}"
fi

# Check if AWS CLI is installed
echo -e "\n${YELLOW}Checking AWS CLI...${NC}"
if command -v aws &> /dev/null; then
    aws_version=$(aws --version)
    echo -e "${GREEN}AWS CLI is installed: $aws_version${NC}"
    
    # Check if AWS credentials are configured
    if aws sts get-caller-identity &> /dev/null; then
        echo -e "${GREEN}AWS credentials are configured.${NC}"
    else
        echo -e "${YELLOW}AWS credentials are not configured.${NC}"
        echo "Run 'aws configure' to set up your AWS credentials."
    fi
else
    echo -e "${YELLOW}AWS CLI is not installed. It is required for cloud deployment.${NC}"
    echo "See https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html for installation instructions."
fi

# Check if Terraform is installed
echo -e "\n${YELLOW}Checking Terraform...${NC}"
if command -v terraform &> /dev/null; then
    terraform_version=$(terraform --version | head -n 1)
    echo -e "${GREEN}Terraform is installed: $terraform_version${NC}"
else
    echo -e "${YELLOW}Terraform is not installed. It is required for infrastructure setup.${NC}"
    echo "See https://learn.hashicorp.com/tutorials/terraform/install-cli for installation instructions."
fi

echo -e "\n${GREEN}=== Setup Complete ===${NC}"
echo -e "To run the TikTok Analyzer, use the following command:"
echo -e "${YELLOW}python run.py --mode=file --input=data/input/usernames.csv --output=data/output/results.csv${NC}"
echo -e "Make sure to create the input CSV file with a 'username' column."
echo -e "\nHappy analyzing!"