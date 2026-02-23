#!/usr/bin/env python3
"""
Verify that Phase 4 secondary conflict chunks are in Supabase
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv(override=True)

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
)

# List of secondary conflict chunk IDs
secondary_chunk_ids = [
    "conflict_eps_exceptions_010_20260224_001",
    "conflict_eps_exceptions_011_20260224_001",
    "conflict_discrimination_010_20260224_001",
    "conflict_discrimination_011_20260224_001",
]

print("=" * 80)
print("VERIFYING PHASE 4 SECONDARY CONFLICT CHUNKS IN SUPABASE")
print("=" * 80)

found_count = 0
not_found = []

for chunk_id in secondary_chunk_ids:
    print(f"\n[Checking] {chunk_id}")

    try:
        result = supabase.table("chunks").select("id, document_short, chapter").eq("id", chunk_id).execute()

        if result.data:
            chunk = result.data[0]
            print(f"  [OK] Found in Supabase")
            print(f"       Document: {chunk['document_short']}")
            print(f"       Chapter: {chunk['chapter'][:60]}...")
            found_count += 1
        else:
            print(f"  [NOT FOUND] Chunk not in database")
            not_found.append(chunk_id)

    except Exception as e:
        print(f"  [ERROR] {str(e)[:80]}")
        not_found.append(chunk_id)

print(f"\n{'=' * 80}")
print(f"SUMMARY: {found_count}/{len(secondary_chunk_ids)} chunks found")

if not_found:
    print(f"\nMissing chunks: {not_found}")
else:
    print(f"\n[OK] All Phase 4 secondary chunks verified in Supabase!")

print(f"{'=' * 80}")
