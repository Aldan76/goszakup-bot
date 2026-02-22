"""
Avtomaticheskoe ispravlenie bazy znaniй
"""
import json
import re
from pathlib import Path
from collections import defaultdict

def fix_missing_source_platform(chunks, filename):
    """Dobavit' source_platform gde ego net"""
    # Opredelit' platformu po imeni faila
    platform_map = {
        'chunks_all': 'all',
        'chunks_dvc': 'dvc',
        'chunks_ktp': 'ktp',
        'chunks_pitanie': 'pitanie',
        'chunks_pravila': 'pravila',
        'chunks_reestrov': 'reestrov',
        'chunks_zakon': 'zakon',
    }
    
    platform = None
    for key, value in platform_map.items():
        if key in filename:
            platform = value
            break
    
    if not platform:
        return chunks, f"Cannot detect platform for {filename}"
    
    fixed = 0
    for chunk in chunks:
        if 'source_platform' not in chunk or not chunk['source_platform']:
            chunk['source_platform'] = platform
            fixed += 1
    
    return chunks, f"Added source_platform='{platform}' to {fixed} chunks"

def fix_chunks_file(filepath):
    """Ispravit' odin fajl"""
    print(f"\nFix: {filepath.name}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    # Fix missing source_platform
    chunks, msg = fix_missing_source_platform(chunks, filepath.name)
    print(f"  {msg}")
    
    # Check for duplicates and assign unique IDs if needed
    id_counts = defaultdict(int)
    for chunk in chunks:
        id_counts[chunk['id']] += 1
    
    duplicates = {id_val: count for id_val, count in id_counts.items() if count > 1}
    
    if duplicates:
        print(f"  Found {len(duplicates)} duplicate IDs:")
        for id_val, count in list(duplicates.items())[:5]:
            print(f"    - '{id_val}': {count} times")
        if len(duplicates) > 5:
            print(f"    ... and {len(duplicates) - 5} more")
    
    # Save fixed file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    
    return True

# Process only files that need fixing
data_dir = Path("data")
files_to_fix = [
    'chunks_all.json',
    'chunks_dvc.json',
    'chunks_ktp.json', 
    'chunks_pitanie.json',
    'chunks_pravila.json',
    'chunks_reestrov.json',
    'chunks_zakon.json',
]

print("FIX KNOWLEDGE BASE")
print("="*70)

for filename in files_to_fix:
    filepath = data_dir / filename
    if filepath.exists():
        fix_chunks_file(filepath)

print("\n" + "="*70)
print("DONE")
