#!/usr/bin/env python3
"""
Debug script for conflicting norms detection
"""

import sys
sys.path.insert(0, '.')

from rag import detect_conflicting_norms, search_supabase, CONFLICTING_NORMS

# Test questions
test_questions = [
    "Можно ли требовать ЭЦП для документов об иностранной регистрации компании?",
    "Можно ли требовать одновременно ISO 9001, 14001 И 45001 как условие участия в закупке на 500 000 тенге?"
]

print("=" * 80)
print("DEBUG: CONFLICTING NORMS DETECTION")
print("=" * 80)

# First, check CONFLICTING_NORMS matrix
print("\n[1] CONFLICTING_NORMS Matrix:")
for conflict_type, config in CONFLICTING_NORMS.items():
    print(f"\n{conflict_type}:")
    print(f"  Keywords: {config.get('keywords', [])[:3]}...")
    print(f"  Positive norms: {config.get('positive_norms', [])}")
    print(f"  Conflicting norms: {config.get('conflicting_norms', [])}")
    print(f"  Chunk IDs: {len(config.get('conflict_chunk_ids', []))} chunks")

# Now test the detection function
print(f"\n{'=' * 80}")
print("[2] TESTING DETECTION FUNCTION:")

for question in test_questions:
    print(f"\n[Q] {question[:70]}...")

    # First, get all relevant chunks to mimic what happens in answer_question
    print("  [a] Searching for base chunks...")
    base_chunks = search_supabase(question, top_n=5, platform="law")
    print(f"      Found {len(base_chunks)} chunks")
    for chunk in base_chunks[:2]:
        print(f"        - {chunk.get('chapter', 'NO CHAPTER')[:50]}")

    # Now test detect_conflicting_norms
    print("  [b] Testing detect_conflicting_norms()...")
    conflict_info = detect_conflicting_norms(question, base_chunks)

    if conflict_info:
        print(f"      [OK] Conflict detected: {conflict_info['type']}")
        print(f"      Positive norms: {conflict_info['positive_norms']}")
        print(f"      Conflicting norms: {conflict_info['conflicting_norms']}")
        print(f"      Chunks found: {len(conflict_info.get('conflicting_chunks', []))}")
        if conflict_info.get('conflicting_chunks'):
            for chunk in conflict_info['conflicting_chunks'][:1]:
                print(f"        - {chunk.get('chapter', 'NO CHAPTER')[:50]}")
    else:
        print(f"      [FAIL] No conflict detected")
        print(f"      Checking why...")

        # Manual check - what keywords match?
        q_lower = question.lower()
        for conflict_type, config in CONFLICTING_NORMS.items():
            keywords = config.get("keywords", [])
            matching = [kw for kw in keywords if kw in q_lower]
            if matching:
                print(f"        - {conflict_type}: matched keywords {matching}")

print(f"\n{'=' * 80}")
