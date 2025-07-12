#!/bin/bash
# Docker build script for eBay TCG Batch Uploader

set -e

# Configuration
IMAGE_NAME="ebay-tcg-uploader"
VERSION="${1:-latest}"
REGISTRY="${2:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building eBay TCG Batch Uploader Docker image...${NC}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

# Check if Dockerfile exists
if [ ! -f "config/docker/Dockerfile" ]; then
    echo -e "${RED}Error: Dockerfile not found!${NC}"
    exit 1
fi

# Build the image
echo -e "${YELLOW}Building image: ${IMAGE_NAME}:${VERSION}${NC}"
docker build -f config/docker/Dockerfile -t ${IMAGE_NAME}:${VERSION} .

# Tag as latest if building a specific version
if [ "${VERSION}" != "latest" ]; then
    docker tag ${IMAGE_NAME}:${VERSION} ${IMAGE_NAME}:latest
    echo -e "${GREEN}Tagged as latest${NC}"
fi

# Tag for registry if specified
if [ -n "${REGISTRY}" ]; then
    docker tag ${IMAGE_NAME}:${VERSION} ${REGISTRY}/${IMAGE_NAME}:${VERSION}
    echo -e "${GREEN}Tagged for registry: ${REGISTRY}/${IMAGE_NAME}:${VERSION}${NC}"
    
    # Push to registry
    echo -e "${YELLOW}Pushing to registry...${NC}"
    docker push ${REGISTRY}/${IMAGE_NAME}:${VERSION}
    
    if [ "${VERSION}" != "latest" ]; then
        docker tag ${IMAGE_NAME}:${VERSION} ${REGISTRY}/${IMAGE_NAME}:latest
        docker push ${REGISTRY}/${IMAGE_NAME}:latest
    fi
fi

# Show image info
echo -e "${GREEN}Build complete!${NC}"
docker images | grep ${IMAGE_NAME}

# Optional: Run security scan
if command -v docker-scan &> /dev/null; then
    echo -e "${YELLOW}Running security scan...${NC}"
    docker scan ${IMAGE_NAME}:${VERSION} || true
fi

echo -e "${GREEN}Done!${NC}"