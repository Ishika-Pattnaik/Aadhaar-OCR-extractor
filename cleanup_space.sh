#!/bin/bash
# Aadhaar OCR Space Cleanup Script
# Run this when you run out of disk space

echo "=== Cleaning up disk space ==="

# Clean pip cache (saves ~1.8GB)
echo "Cleaning pip cache..."
pip cache purge 2>/dev/null || rm -rf ~/Library/Caches/pip

# Clean Spotify cache (saves ~5GB)
echo "Cleaning Spotify cache..."
rm -rf ~/Library/Caches/com.spotify.client 2>/dev/null

# Clean Google Chrome cache (saves ~800MB)
echo "Cleaning Google cache..."
rm -rf ~/Library/Caches/Google 2>/dev/null

# Clean temporary files
echo "Cleaning temp files..."
rm -rf /tmp/*.jpg 2>/dev/null
rm -rf ~/tmp/* 2>/dev/null

# Clean HuggingFace cache (optional, will re-download models)
echo "Cleaning HuggingFace cache..."
# rm -rf ~/.cache/huggingface 2>/dev/null

# Clean PaddleOCR cache
echo "Cleaning PaddleOCR cache..."
rm -rf ~/.cache/paddle 2>/dev/null

echo "=== Cleanup complete! ==="
echo ""
echo "Disk usage now:"
df -h / | tail -1

