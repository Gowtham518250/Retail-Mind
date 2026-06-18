#!/bin/bash
# 🚀 AI SHOP PRO - QUICK TEST RUNNER
# This script tests all endpoints with the provided database

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     🧪 AI SHOP PRO - ENDPOINT TESTING SUITE LAUNCHER          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if .env.production exists
if [ ! -f .env.production ]; then
    echo -e "${RED}❌ .env.production file not found!${NC}"
    echo "Please create .env.production with DATABASE_URL"
    exit 1
fi

echo -e "${GREEN}✅ .env.production found${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 3 found: $(python3 --version)${NC}"

# Install requirements
echo -e "\n${YELLOW}📦 Installing dependencies...${NC}"
pip install -r requirements.txt --quiet

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Dependencies installed${NC}"

# Start test
echo -e "\n${BLUE}Starting comprehensive endpoint tests...${NC}\n"
python3 test_all_endpoints_comprehensive.py

# Capture exit code
EXIT_CODE=$?

echo -e "\n${BLUE}════════════════════════════════════════════════════════════════${NC}"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
else
    echo -e "${RED}⚠️  Some tests failed - check test_report_*.json for details${NC}"
fi

exit $EXIT_CODE
