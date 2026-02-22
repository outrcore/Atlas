#!/bin/bash
cd /workspace/Jarvis
echo "Building..."
pnpm build 2>&1 | tail -5
echo "Starting gateway..."
pnpm openclaw gateway
