"""
Isправit' skhemu chunks_civil_code.json chtoby sootvetstvovati standartnomu formatu
"""
import json
from pathlib import Path

def fix_civil_code_schema():
    """Fix field names in civil_code chunks"""
    filepath = Path("data/chunks_civil_code.json")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    print(f"Processing {len(chunks)} chunks...")
    
    fixed_count = 0
    for chunk in chunks:
        # Rename 'content' to 'text'
        if 'content' in chunk and 'text' not in chunk:
            chunk['text'] = chunk.pop('content')
            fixed_count += 1
        
        # Rename 'article_url' to 'official_url'
        if 'article_url' in chunk and 'official_url' not in chunk:
            chunk['official_url'] = chunk.pop('article_url')
        
        # Add 'document_short' if missing
        if 'document_short' not in chunk:
            chunk['document_short'] = 'Grazhdanskij kodeks RK'
        
        # Ensure source_platform is set
        if 'source_platform' not in chunk:
            chunk['source_platform'] = 'civil_code'
    
    # Save fixed file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    
    print(f"Fixed {fixed_count} chunks")
    print("Renamed: content -> text, article_url -> official_url")
    print("Added: document_short='Grazhdanskij kodeks RK'")
    print("\nDone!")

if __name__ == '__main__':
    fix_civil_code_schema()
