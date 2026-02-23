#!/usr/bin/env python3
"""
Upload Phase 4 SECONDARY conflicting norms chunks to Supabase
Processes chunks_conflicting_norms_secondary.json and uploads to chunks table
"""

import json
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv(override=True)

# Initialize Supabase
supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
)

# Load secondary chunks
with open("data/chunks_conflicting_norms_secondary.json", encoding="utf-8") as f:
    chunks = json.load(f)

print("=" * 80)
print("UPLOADING PHASE 4 SECONDARY CONFLICTING NORMS CHUNKS")
print("=" * 80)

uploaded_count = 0
error_count = 0

for i, chunk in enumerate(chunks, 1):
    print(f"\n[{i}/{len(chunks)}] Processing: {chunk['id']}")
    print(f"    Title: {chunk['document_name'][:60]}")

    # Prepare data for Supabase
    data = {
        "id": chunk["id"],
        "document_short": chunk["document_short"],
        "document_name": chunk["document_name"],
        "source_type": chunk["source_type"],
        "source_platform": chunk["source_platform"],
        "chapter": chunk["chapter"],
        "text": chunk["text"],
        "official_url": chunk["official_url"],
    }

    try:
        # Upsert (insert or update if exists)
        result = supabase.table("chunks").upsert(data).execute()

        if result.data:
            print(f"    [OK] Uploaded successfully")
            uploaded_count += 1
        else:
            print(f"    [WARN] Response empty (may still be uploaded)")
            uploaded_count += 1

    except Exception as e:
        print(f"    [ERROR] {str(e)[:100]}")
        error_count += 1

# Summary
print(f"\n{'=' * 80}")
print("UPLOAD SUMMARY")
print(f"{'=' * 80}")
print(f"Uploaded: {uploaded_count}/{len(chunks)}")
print(f"Errors: {error_count}")

if error_count == 0:
    print(f"\n[OK] Phase 4 secondary chunks uploaded successfully!")
else:
    print(f"\n[WARN] Some chunks failed to upload - check errors above")

print(f"{'=' * 80}")
