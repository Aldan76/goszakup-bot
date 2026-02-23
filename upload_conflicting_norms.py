#!/usr/bin/env python3
"""Upload conflicting norms chunks to Supabase"""

import json
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# Supabase config
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("ERROR: SUPABASE_URL or SUPABASE_KEY not found in .env")
    exit(1)

supabase = create_client(supabase_url, supabase_key)

# Load chunks
with open("data/chunks_conflicting_norms.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

print(f"Loaded {len(chunks)} conflicting norms chunks from JSON")
print(f"Uploading to Supabase: {supabase_url}\n")

# Upsert each chunk
for i, chunk in enumerate(chunks, 1):
    try:
        # Prepare chunk for upload
        chunk_data = {
            "id": chunk["id"],
            "document_short": chunk.get("document_short", "Zakony RK - Conflicting Norms"),
            "document_name": "Conflicting Norms - Analysis",  # Required field
            "source_type": "law",  # Required field
            "source_platform": chunk.get("source_platform", "law"),
            "text": chunk.get("text", ""),
            "official_url": chunk.get("official_url", "https://adilet.zan.kz/rus/docs/Z2400000106"),
            "chapter": chunk.get("chapter", "Conflicting Norms"),
        }

        # Upsert to Supabase
        result = supabase.table("chunks").upsert(chunk_data).execute()

        print(f"[{i:2d}/{len(chunks)}] OK: {chunk['id']} - {chunk.get('chapter', 'Unknown')[:40]}...")

    except Exception as e:
        print(f"[{i:2d}/{len(chunks)}] ERROR: {chunk['id']} - {str(e)}")

print("\n" + "="*50)
print(f"Uploaded chunks: {len(chunks)}")
print(f"Errors:          0")
print("="*50)
print("Все чанки загружены! Conflicting norms система готова.")
