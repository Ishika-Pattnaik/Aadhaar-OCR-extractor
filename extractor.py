import re
import logging
from config import AADHAAR_REGEX_PATTERNS, OCR_CORRECTIONS, NAME_ANCHORS_TOP, NON_NAME_WORDS, AADHAAR_CONFIDENCE_THRESHOLD
from validator import Validator

logger = logging.getLogger(__name__)

class Extractor:
    def __init__(self):
        self.validator = Validator()

    def clean_ocr_text(self, text):
        """
        Cleans OCR text by fixing common confusions.
        e.g. '1234 567B' -> '1234 5678'
        """
        res = ""
        for char in text:
            if char in OCR_CORRECTIONS:
                res += OCR_CORRECTIONS[char]
            else:
                res += char
        return res.strip()



    def is_valid_name(self, text):
        """
        Validates if extracted text could be a person's name.
        Returns True if it passes name criteria, False otherwise.
        """
        if not text or not text.strip():
            return False
        
        text_lower = text.lower().strip()
        words = text_lower.split()
        
        # Must have at least 2 words to be a name (first name + last name)
        if len(words) < 2:
            logger.debug(f"Rejected name '{text}': Less than 2 words")
            return False
        
        # Filter out text containing non-name words (using word boundary matching)
        for non_name in NON_NAME_WORDS:
            # Use regex with word boundaries to avoid substring matches
            # e.g., "m" should only match " m ", not "kumar"
            pattern = r'\b' + re.escape(non_name) + r'\b'
            if re.search(pattern, text_lower):
                logger.debug(f"Rejected name '{text}': Contains non-name word '{non_name}'")
                return False
        
        # Check if text starts with digits (unlikely for names)
        if text.strip()[0].isdigit():
            logger.debug(f"Rejected name '{text}': Starts with digit")
            return False
        
        # Check if text is too long (likely not a name, more likely a sentence/address)
        if len(words) > 6:
            logger.debug(f"Rejected name '{text}': Too many words ({len(words)})")
            return False
        
        # Reject if all words are uppercase and very long (likely a header/label)
        if text.isupper() and len(text) > 20:
            logger.debug(f"Rejected name '{text}': All caps and too long")
            return False
        
        # Reject if text contains special characters (except hyphens/apostrophes in names)
        # Allow spaces, hyphens, and apostrophes
        if re.search(r'[^\w\s\-\']', text):
            # Check if it contains only allowed special chars
            clean_text = re.sub(r'[\w\s\-\']', '', text)
            if clean_text.strip():
                logger.debug(f"Rejected name '{text}': Contains invalid special characters")
                return False
        
        return True

    def extract_aadhaar_number(self, ocr_results):
        """
        Scans all OCR lines for a valid 12-digit Aadhaar number.
        Returns: (number_string, confidence_score)
        """
        if not ocr_results:
            logger.warning("No OCR results provided")
            return None, 0.0

        # DEBUG: Log ALL OCR results
        logger.info(f"Scanning {len(ocr_results)} OCR items for Aadhaar number...")
        logger.debug("=== ALL OCR RESULTS ===")
        for i, item in enumerate(ocr_results):
            text = item.get('text', '')
            conf = item.get('conf', 0)
            logger.debug(f"  [{i}] text='{text}' conf={conf:.2f}")
        
        all_digits = []
        for item in ocr_results:
            text = item['text']
            conf = item['conf']
            # Extract all digit sequences
            digit_seqs = re.findall(r'\d+', text)
            for seq in digit_seqs:
                all_digits.append((seq, conf, text))  # Include original text for context

        logger.info(f"Found {len(all_digits)} digit sequences")
        logger.debug("=== DIGIT SEQUENCES ===")
        for seq, conf, orig in all_digits:
            logger.debug(f"  digits='{seq}' from='{orig}' conf={conf:.2f}")

        best_candidate = None
        max_conf = 0.0
        best_is_valid = False

        # Strategy 0: Handle cases where one OCR line has multiple digit sequences
        # e.g., "3492 1290" -> two sequences that should be combined
        logger.info("Trying multi-sequence combination from same line...")
        for item in ocr_results:
            text = item['text']
            conf = item['conf']
            
            if conf < AADHAAR_CONFIDENCE_THRESHOLD:
                continue

            cleaned = self.clean_ocr_text(text)
            # Find all digit sequences in this line
            digit_seqs = re.findall(r'\d+', cleaned)
            
            if len(digit_seqs) >= 2:
                # Try combining all sequences from this line
                combined = "".join(digit_seqs)
                if len(combined) >= 12:
                    num12 = combined[:12]
                    is_valid = self.validator.validate_verhoeff(num12)
                    logger.debug(f"Multi-seq from '{text}': {num12}, valid: {is_valid}")
                    if conf > max_conf:
                        max_conf = conf
                        best_candidate = num12
                        best_is_valid = is_valid
        
        # Strategy 0b: Combine adjacent multi-seq items with single-seq items
        # This handles the case where "3492 1290" and "8697" are separate items
        # and need to be combined in the right order
        logger.info("Trying cross-item combination for multi-seq lines...")
        
        # Find items with 2+ digit sequences
        multi_seq_items = []
        for idx, item in enumerate(ocr_results):
            text = item['text']
            conf = item['conf']
            if conf < AADHAAR_CONFIDENCE_THRESHOLD:
                continue
            cleaned = self.clean_ocr_text(text)
            digit_seqs = re.findall(r'\d+', cleaned)
            if len(digit_seqs) >= 2:
                multi_seq_items.append({
                    'index': idx,
                    'text': text,
                    'conf': conf,
                    'combined': "".join(digit_seqs),
                    'total_len': len("".join(digit_seqs))
                })
        
        # Find single-seq items
        single_seq_items = []
        for idx, item in enumerate(ocr_results):
            text = item['text']
            conf = item['conf']
            if conf < AADHAAR_CONFIDENCE_THRESHOLD:
                continue
            cleaned = self.clean_ocr_text(text)
            digit_seqs = re.findall(r'\d+', cleaned)
            if len(digit_seqs) == 1 and len(digit_seqs[0]) >= 4:
                single_seq_items.append({
                    'index': idx,
                    'text': text,
                    'conf': conf,
                    'digits': digit_seqs[0],
                    'len': len(digit_seqs[0])
                })
        
        logger.debug(f"Multi-seq items: {len(multi_seq_items)}, Single-seq items: {len(single_seq_items)}")
        
        # Try combining: single item + multi-seq item (order matters!)
        for single in single_seq_items:
            for multi in multi_seq_items:
                # Skip if items are the same
                if single['index'] == multi['index']:
                    continue
                
                single_digits = single['digits']
                multi_combined = multi['combined']
                
                # Try: single_digits + multi_combined
                if len(single_digits) + len(multi_combined) >= 12:
                    combined = single_digits + multi_combined
                    num12 = combined[:12]
                    is_valid = self.validator.validate_verhoeff(num12)
                    avg_conf = (single['conf'] + multi['conf']) / 2
                    logger.debug(f"Cross-combo (single+multi): '{single['text']}' + '{multi['text']}' = {num12}, valid: {is_valid}")
                    if avg_conf > max_conf:
                        max_conf = avg_conf
                        best_candidate = num12
                        best_is_valid = is_valid
                
                # Try: multi_combined + single_digits
                if len(multi_combined) + len(single_digits) >= 12:
                    combined = multi_combined + single_digits
                    num12 = combined[:12]
                    is_valid = self.validator.validate_verhoeff(num12)
                    avg_conf = (single['conf'] + multi['conf']) / 2
                    logger.debug(f"Cross-combo (multi+single): '{multi['text']}' + '{single['text']}' = {num12}, valid: {is_valid}")
                    if avg_conf > max_conf:
                        max_conf = avg_conf
                        best_candidate = num12
                        best_is_valid = is_valid

        # Strategy 1: Look for direct match using Configured Patterns & Cleaning
        for item in ocr_results:
            text = item['text']
            conf = item['conf']
            
            # Skip low confidence results
            if conf < AADHAAR_CONFIDENCE_THRESHOLD:
                logger.debug(f"Skipping low confidence text: '{text}' ({conf:.2f})")
                continue
            
            # Apply robust cleaning (fixes B->8, O->0 etc)
            cleaned_text = self.clean_ocr_text(text)
            
            # Check against configured Regex Patterns (e.g. "1234 5678 9012")
            for pattern in AADHAAR_REGEX_PATTERNS:
                matches = re.findall(pattern, cleaned_text)
                for match in matches:
                    logger.debug(f"Regex match: '{match}' from '{text}'")
                     # Remove spaces for validation
                    clean_num = match.replace(" ", "")
                    if len(clean_num) == 12:
                         is_valid = self.validator.validate_verhoeff(clean_num)
                         logger.debug(f"Aadhaar candidate: {clean_num}, valid: {is_valid}, conf: {conf}")
                         if conf > max_conf:
                            max_conf = conf
                            best_candidate = clean_num
                            best_is_valid = is_valid

            # Fallback: Check for any 12-digit sequence in the cleaned line
            # This handles cases not strictly matching the regex (e.g. weird spacing)
            clean_digits_only = cleaned_text.replace(" ", "")
            matches = re.findall(r'\b\d{12}\b', clean_digits_only)
            for match in matches:
                 is_valid = self.validator.validate_verhoeff(match)
                 logger.debug(f"12-digit match: {match}, valid: {is_valid}")
                 # Only update if we haven't found a stronger match or if this has higher confidence
                 if conf > max_conf: 
                        max_conf = conf
                        best_candidate = match
                        best_is_valid = is_valid

        # Strategy 2: Combine 4-digit + 8-digit sequences (with cleaning)
        logger.info("Trying 4+8 digit combination strategy...")
        for i, (seq1, conf1, orig1) in enumerate(all_digits):
            seq1_clean = self.clean_ocr_text(seq1) # Clean individual chunks too
            if len(seq1_clean) == 4 and seq1_clean.isdigit():
                for j, (seq2, conf2, orig2) in enumerate(all_digits):
                    if i != j:
                        seq2_clean = self.clean_ocr_text(seq2)
                        if len(seq2_clean) >= 8 and seq2_clean[:8].isdigit():
                            # Try combining: 4 digits + next 8 digits from seq2
                            combined = seq1_clean + seq2_clean[:8]
                            if len(combined) == 12:
                                is_valid = self.validator.validate_verhoeff(combined)
                                avg_conf = (conf1 + conf2) / 2
                                logger.debug(f"4+8 combination: {combined}, valid: {is_valid}, avg_conf: {avg_conf:.2f}")
                                if avg_conf > max_conf:
                                    max_conf = avg_conf
                                    best_candidate = combined
                                    best_is_valid = is_valid

        # Strategy 3: Look for 6-digit + 6-digit patterns (with cleaning)
        logger.info("Trying 6+6 digit combination strategy...")
        for i, (seq1, conf1, orig1) in enumerate(all_digits):
            seq1_clean = self.clean_ocr_text(seq1)
            if len(seq1_clean) == 6 and seq1_clean.isdigit():
                for j, (seq2, conf2, orig2) in enumerate(all_digits):
                    if i != j:
                        seq2_clean = self.clean_ocr_text(seq2)
                        if len(seq2_clean) == 6 and seq2_clean.isdigit():
                            combined = seq1_clean + seq2_clean
                            is_valid = self.validator.validate_verhoeff(combined)
                            avg_conf = (conf1 + conf2) / 2
                            logger.debug(f"6+6 combination: {combined}, valid: {is_valid}, avg_conf: {avg_conf:.2f}")
                            if avg_conf > max_conf:
                                max_conf = avg_conf
                                best_candidate = combined
                                best_is_valid = is_valid

        # Strategy 4: Look for any 12 consecutive digits anywhere
        logger.info("Trying 12-digit scan strategy...")
        for item in ocr_results:
            text = item['text']
            conf = item['conf']
            
            if conf < AADHAAR_CONFIDENCE_THRESHOLD:
                continue
            
            cleaned = self.clean_ocr_text(text)
            # Find any sequence of 12+ digits
            matches = re.findall(r'\d{12,}', cleaned)
            for match in matches:
                # Take first 12 digits
                num12 = match[:12]
                is_valid = self.validator.validate_verhoeff(num12)
                logger.debug(f"12+ digit scan: {num12}, valid: {is_valid}")
                if conf > max_conf:
                    max_conf = conf
                    best_candidate = num12
                    best_is_valid = is_valid

        if best_candidate:
            formatted = f"{best_candidate[:4]} {best_candidate[4:8]} {best_candidate[8:]}"
            logger.info(f"Found Aadhaar: {formatted} (valid: {best_is_valid}, conf: {max_conf:.2f})")
            return formatted, max_conf
        else:
            logger.warning("No valid Aadhaar number found in OCR results")
        
        return None, 0.0

    def extract_name(self, ocr_results, user_name_hint=None):
        """
        Extracts name based on anchors or fuzzy matching with user hint.
        Validates that extracted text is a valid person's name using is_valid_name().
        Returns: (name_string, confidence_score)
        """
        # Strategy 1: If user provided a name, look for it (fuzzy match)
        if user_name_hint:
            best_match = None
            best_score = 0
            best_conf = 0.0
            
            for item in ocr_results:
                text = item['text']
                conf = item.get('conf', 0.0)
                # First check if it's a valid name format
                if not self.is_valid_name(text):
                    continue
                passed, score = self.validator.fuzzy_match_name(text, user_name_hint)
                if passed and score > best_score:
                    best_score = score
                    best_match = text
                    best_conf = conf
            
            if best_match:
                return best_match, best_conf
        
        # Strategy 2: Heuristic / Spatial
        # Find "Government of India" / "Govt of India"
        # The line physically BELOW it is often the Name.
        
        govt_index = -1
        for i, item in enumerate(ocr_results):
            txt = item['text'].lower()
            if "govt" in txt or "government" in txt:
                govt_index = i
                break
        
        if govt_index != -1 and govt_index + 1 < len(ocr_results):
            # Candidate is the next line
            item = ocr_results[govt_index + 1]
            candidate = item['text']
            conf = item.get('conf', 0.0)
            
            # Use is_valid_name() for comprehensive validation
            # This replaces the old ad-hoc checks for dob/male/female
            if self.is_valid_name(candidate):
                logger.debug(f"Valid name found below government: '{candidate}'")
                return candidate, conf
            else:
                # Try looking at more lines below if immediate next line failed validation
                for offset in range(2, 5):  # Check next 3 lines
                    if govt_index + offset < len(ocr_results):
                        item = ocr_results[govt_index + offset]
                        next_candidate = item['text']
                        conf = item.get('conf', 0.0)
                        if self.is_valid_name(next_candidate):
                            logger.debug(f"Valid name found {offset} lines below government: '{next_candidate}'")
                            return next_candidate, conf
        
        # Strategy 3: Look for text above DOB/Gender anchors that looks like a name
        for i, item in enumerate(ocr_results):
            txt = item['text'].lower()
            if any(anchor in txt for anchor in ["dob", "year of birth", "gender", "male", "female"]):
                # Check the line above
                if i > 0:
                    item = ocr_results[i - 1]
                    candidate = item['text']
                    conf = item.get('conf', 0.0)
                    if self.is_valid_name(candidate):
                        logger.debug(f"Valid name found above DOB/gender: '{candidate}'")
                        return candidate, conf
        
        # Strategy 4: Scan all OCR results for any valid name-like text
        # This is a fallback for documents where anchor-based extraction failed
        for item in ocr_results:
            text = item['text']
            conf = item.get('conf', 0.0)
            if self.is_valid_name(text):
                # Additional check: ensure it has at least one capital letter (proper noun indicator)
                has_capital = any(c.isupper() for c in text)
                if has_capital:
                    logger.debug(f"Valid name found via scan: '{text}'")
                    return text, conf
        
        return "", 0.0
