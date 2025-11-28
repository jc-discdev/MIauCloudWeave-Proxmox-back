#!/bin/bash
# Test script for Proxmox API

API_URL="http://localhost:8001"

echo "🧪 Testing Proxmox API..."
echo ""

# Test 1: API Root
echo "1️⃣ Testing API root..."
curl -s $API_URL | jq .
echo ""

# Test 2: Proxmox Connection
echo "2️⃣ Testing Proxmox connection..."
curl -s $API_URL/proxmox/test | jq .
echo ""

# Test 3: List VMs
echo "3️⃣ Listing VMs and containers..."
curl -s $API_URL/proxmox/list | jq .
echo ""

# Test 4: Create a test LXC container (commented out by default)
# echo "4️⃣ Creating test LXC container..."
# curl -s -X POST $API_URL/proxmox/create \
#   -H "Content-Type: application/json" \
#   -d '{
#     "name": "test-container",
#     "vm_type": "lxc",
#     "cores": 1,
#     "memory": 512,
#     "disk_size": 8
#   }' | jq .
# echo ""

# Test 5: Get credentials
echo "5️⃣ Getting stored credentials..."
curl -s $API_URL/credentials | jq .
echo ""

echo "✅ Tests completed!"
