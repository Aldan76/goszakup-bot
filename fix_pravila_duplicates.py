"""
Isправit' dubliruuyushchie ID v chunks_pravila.json
"""
import json
import hashlib
from pathlib import Path
from collections import defaultdict

def fix_pravila_duplicates():
    """Fix duplicate IDs in pravila chunks"""
    filepath = Path("data/chunks_pravila.json")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    print(f"Processing {len(chunks)} chunks...")
    
    # Find duplicates
    id_counts = defaultdict(int)
    for chunk in chunks:
        id_counts[chunk['id']] += 1
    
    duplicates = {id_val: count for id_val, count in id_counts.items() if count > 1}
    print(f"Found {len(duplicates)} duplicate IDs")
    
    # Fix duplicates by appending sequence number
    id_sequence = defaultdict(int)
    fixed_count = 0
    
    for chunk in chunks:
        chunk_id = chunk['id']
        if chunk_id in duplicates:
            id_sequence[chunk_id] += 1
            # Generate new unique ID
            title = chunk.get('article_title', '').encode('utf-8')
            hash_suffix = hashlib.md5(title).hexdigest()[:8]
            new_id = f"pravila_{hash_suffix}_{id_sequence[chunk_id]:03d}"
            
            print(f"  {chunk_id} -> {new_id}")
            chunk['id'] = new_id
            fixed_count += 1
    
    # Save fixed file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    
    print(f"\nFixed {fixed_count} duplicate IDs")
    print("Done!")

if __name__ == '__main__':
    fix_pravila_duplicates()
