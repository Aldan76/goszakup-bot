"""
Proverit' bazу znaniй na oshibki
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

def check_chunks_file(filepath):
    """Proverit' fajl s chunkamі na oshibki"""
    print(f"\n{'='*70}")
    print(f"CHECK: {filepath.name}")
    print(f"{'='*70}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR JSON: {e}")
        return False
    
    if not isinstance(chunks, list):
        print(f"ERROR: Root is not list (found {type(chunks).__name__})")
        return False
    
    print(f"OK: JSON valid, {len(chunks)} chunks")
    
    errors = []
    warnings = []
    ids_seen = defaultdict(list)
    
    for i, chunk in enumerate(chunks):
        # Proverit' obazytel'nye polya
        required_fields = ['id', 'document_short', 'source_platform', 'text']
        for field in required_fields:
            if field not in chunk:
                errors.append(f"  [{i}] Missing field '{field}'")
            elif not chunk[field] or (isinstance(chunk[field], str) and not chunk[field].strip()):
                errors.append(f"  [{i}] Empty field '{field}'")
        
        # Proverit' dublirovanie ID
        if 'id' in chunk:
            ids_seen[chunk['id']].append(i)
        
        # Proverit' opechatkі v source_platform
        if 'source_platform' in chunk:
            platform = chunk['source_platform']
            valid_platforms = ['law', 'omarket', 'goszakup', 'civil_code', 'tax', 
                             'dvc', 'ktp', 'pitanie', 'pravila', 'reestrov', 'zakon', 'all']
            if platform not in valid_platforms:
                warnings.append(f"  [{i}] Unknown platform: '{platform}'")
        
        # Proverit' kontenta
        if 'text' in chunk and chunk['text']:
            text = chunk['text']
            # Proverit' na markery stranic
            if '=== PAGE:' in text or '=== END ===' in text:
                errors.append(f"  [{i}] Page markers found (=== PAGE: or === END ===)")
            # Proverit' na pustoj kontent
            if len(text.strip()) < 20:
                warnings.append(f"  [{i}] Very short content ({len(text)} chars)")
            # Proverit' na HTML tegi
            if '<' in text and '>' in text:
                if '<html' in text.lower() or '<script' in text.lower() or '<div' in text.lower():
                    errors.append(f"  [{i}] Contains HTML tags")
    
    # Dubliruuyushchie ID
    duplicates = {id_val: indices for id_val, indices in ids_seen.items() if len(indices) > 1}
    if duplicates:
        for id_val, indices in duplicates.items():
            errors.append(f"  DUPLICATE ID '{id_val}': positions {indices}")
    
    if errors:
        print(f"\nERRORS ({len(errors)}):")
        for err in errors:
            print(err)
    
    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for warn in warnings[:10]:
            print(warn)
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")
    
    if not errors and not warnings:
        print("OK: All good")
        return True
    
    return len(errors) == 0

# Proverit' vse faili
data_dir = Path("data")
json_files = sorted(data_dir.glob("chunks_*.json"))

print("CHECK KNOWLEDGE BASE")
print("="*70)

all_ok = True
for filepath in json_files:
    if not check_chunks_file(filepath):
        all_ok = False

print(f"\n{'='*70}")
if all_ok:
    print("OK: ALL FILES GOOD")
else:
    print("ERRORS FOUND - see above")
print("="*70)
