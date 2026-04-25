#!/usr/bin/env python3
"""
Debug script to see exactly what PaddleOCR detects from an image.
"""
import sys
import os

# Disable model source check before importing
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

sys.path.insert(0, '.')

from preprocessor import Preprocessor
from ocr_engine import OCREngine
from validator import Validator
from config import AADHAAR_REGEX_PATTERNS
import re

# Initialize
print("Initializing OCR components...")
preprocessor = Preprocessor()
ocr_engine = OCREngine()
validator = Validator()
print("Initialization complete!\n")

# Test image
image_path = '/Users/sujit/aadhaar-ocr-1/96562d89712741a88b6986a1cfc2b2a6.jpg'

print("=" * 60)
print("AADHAAR OCR DEBUG SCRIPT")
print("=" * 60)

# Preprocess
print("\n[1] PREPROCESSING...")
gray_img, bin_img = preprocessor.preprocess_pipeline(image_path)
print(f"   Gray image shape: {gray_img.shape}")

# OCR
print("\n[2] RUNNING OCR...")
results = ocr_engine.extract_text(gray_img)
print(f"   Total OCR items: {len(results)}")

# Print all OCR results
print("\n[3] ALL OCR RESULTS:")
print("-" * 60)
for i, item in enumerate(results):
    text = item.get('text', '')
    conf = item.get('conf', 0)

    # Check for digits
    digits = re.findall(r'\d+', text)
    digit_info = f" [DIGITS: {digits}]" if digits else ""

    print(f"{i+1:2d}. \"{text}\" {digit_info}")
    print(f"     Confidence: {conf:.2f}")

# Look for Aadhaar patterns
print("\n[4] LOOKING FOR AADHAAR PATTERNS:")
print("-" * 60)

all_digits = []
for item in results:
    text = item['text']
    conf = item['conf']
    digit_seqs = re.findall(r'\d+', text)
    for seq in digit_seqs:
        all_digits.append((seq, conf, text))

print(f"Total digit sequences found: {len(all_digits)}")
for seq, conf, orig in all_digits:
    print(f"   \"{orig}\" -> digits: {seq} (conf: {conf:.2f})")

# Try finding Aadhaar patterns
print("\n[5] TRYING AADHAAR PATTERNS:")
print("-" * 60)

for item in results:
    text = item['text']
    conf = item['conf']

    for pattern in AADHAAR_REGEX_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            for match in matches:
                clean = match.replace(" ", "")
                print(f"   Pattern '{pattern}' matched: '{match}' -> {clean}")
                if len(clean) == 12:
                    is_valid = validator.validate_verhoeff(clean)
                    print(f"      Verhoeff validation: {is_valid}")

# Try combining digits
print("\n[6] TRYING TO COMBINE DIGITS:")
print("-" * 60)

# Build all digit sequences
digit_list = []
for seq, conf, orig in all_digits:
    clean_seq = re.sub(r'[ODQBIil|ISZBALA]', '0', seq.replace('O', '0').replace('D', '0'))
    if clean_seq.isdigit():
        digit_list.append((clean_seq, conf, orig))

print(f"Clean digit sequences: {len(digit_list)}")
for seq, conf, orig in digit_list:
    print(f"   {seq} (conf: {conf:.2f}) from: \"{orig}\"")

# Try 4+8 combination
print("\n   Trying 4+8 combination:")
for i, (seq1, conf1, orig1) in enumerate(digit_list):
    if len(seq1) == 4:
        for j, (seq2, conf2, orig2) in enumerate(digit_list):
            if i != j and len(seq2) >= 8:
                combined = seq1 + seq2[:8]
                if len(combined) == 12:
                    is_valid = validator.validate_verhoeff(combined)
                    print(f"   FOUND: {combined} (valid: {is_valid})")
                    print(f"      From: \"{orig1}\" + \"{orig2[:8]}\"")

# Try 6+6 combination
print("\n   Trying 6+6 combination:")
for i, (seq1, conf1, orig1) in enumerate(digit_list):
    if len(seq1) == 6:
        for j, (seq2, conf2, orig2) in enumerate(digit_list):
            if i != j and len(seq2) == 6:
                combined = seq1 + seq2
                is_valid = validator.validate_verhoeff(combined)
                print(f"   {combined} (valid: {is_valid})")
                print(f"      From: \"{orig1}\" + \"{orig2}\"")

# Try other combinations
print("\n   Trying other combinations:")
total_digits = "".join([d[0] for d in digit_list])
print(f"   All digits concatenated: {total_digits}")
if len(total_digits) >= 12:
    for i in range(len(total_digits) - 11):
        candidate = total_digits[i:i+12]
        if validator.validate_verhoeff(candidate):
            print(f"   *** FOUND: {candidate} ***")

print("\n" + "=" * 60)
print("END OF DEBUG OUTPUT")
print("=" * 60)

