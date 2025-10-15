#!/bin/bash
# Quick test of voice system

cd /Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/voice

echo "🎤 Testing Voice System..."
echo
echo "OpenAI API Key: $(grep OPENAI_API_KEY .env | cut -d'=' -f1)=$(grep OPENAI_API_KEY .env | cut -d'=' -f2 | cut -c1-20)..."
echo
echo "Running Example 1: Basic Voice Session"
echo "This will simulate voice commands to Kaya"
echo
echo "Commands it will test:"
echo "  1. 'Kaya, write a test for user login'"
echo "  2. 'Kaya, run tests/login.spec.ts'"
echo "  3. 'Kaya, validate the checkout flow'"
echo
echo "Press Enter to start..."
read

node dist/examples.js 1
