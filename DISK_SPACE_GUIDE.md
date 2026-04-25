# Aadhaar OCR - Disk Space Management Guide

## The Problem
Running the Aadhaar OCR interface can consume significant disk space due to:
1. **PaddleOCR models**: ~500MB-1GB (downloaded once, then cached)
2. **HuggingFace cache**: ~500MB (for ML models)
3. **pip cache**: ~1.8GB (Python packages)
4. **Spotify cache**: ~5GB (if you use Spotify)
5. **Google Chrome cache**: ~800MB

## Quick Fix - Run Cleanup Script
When you run out of space, run the cleanup script:

```bash
cd /Users/sujit/aadhaar-ocr-1
chmod +x cleanup_space.sh
./cleanup_space.sh
```

## Prevention Tips

### 1. Before Running the Server
Clean up space first:
```bash
pip cache purge
rm -rf ~/Library/Caches/com.spotify.client
```

### 2. Limit pip Cache
Pip can accumulate large caches. Limit it:
```bash
pip config set global.cache-dir ~/.cache/pip
```

### 3. Use Smaller OCR Model
The default PaddleOCR model is comprehensive but large. For lighter usage, consider:
- Using `lang='en'` instead of multilingual models
- Models will be cached in `~/.cache/paddle`

### 4. Clean Up After Each Run
After processing images:
```bash
rm -rf /tmp/aadhaar_*.jpg
```

## Disk Space Monitoring
Check available space:
```bash
df -h /
```

Check large directories:
```bash
du -sh ~/Library/Caches/* | sort -rh | head -10
```

## Estimated Space Requirements
- Fresh install: ~2-3GB
- After first OCR run: ~3-4GB (models cached)
- Safe to keep free: 5GB minimum

## If You Continue to Have Issues
1. Restart your computer to clear temporary files
2. Check for large files: `find ~ -type f -size +100M 2>/dev/null`
3. Consider using an external SSD for the project

