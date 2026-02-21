"""
upload_reestrov.py — Загружает чанки Правил реестров №646 в Supabase
через REST API (urllib, без supabase-py).
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')

# Загружаем .env вручную
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, '.env')
env = {}
with open(env_path, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

SUPABASE_URL = env['SUPABASE_URL']
SUPABASE_KEY = env['SUPABASE_KEY']

chunks_path = os.path.join(BASE_DIR, 'data', 'chunks_reestrov.json')
with open(chunks_path, encoding='utf-8') as f:
    chunks = json.load(f)

print(f"Чанков для загрузки: {len(chunks)}")
print(f"Supabase: {SUPABASE_URL}")
print()

success = 0
errors = 0

for i, chunk in enumerate(chunks):
    row = {
        "id":             chunk["id"],
        "document_short": chunk["document_short"],
        "document_name":  chunk["document_name"],
        "source_type":    chunk["source_type"],
        "chapter":        chunk.get("chapter"),
        "chapter_num":    chunk.get("chapter_num"),
        "article_num":    chunk.get("article_num"),
        "article_title":  chunk.get("article_title"),
        "punkt_range":    chunk.get("punkt_range"),
        "text":           chunk["text"],
        "official_url":   chunk["official_url"],
        "char_count":     chunk["char_count"],
    }

    body = json.dumps(row).encode('utf-8')
    url = f"{SUPABASE_URL}/rest/v1/chunks"

    req = urllib.request.Request(
        url,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer': 'resolution=merge-duplicates',  # upsert
        }
    )

    try:
        with urllib.request.urlopen(req) as resp:
            success += 1
            title = (chunk.get("article_title") or chunk.get("chapter", ""))[:55]
            print(f"  [{i+1:2d}/{len(chunks)}] OK: {chunk['id']} — {title}")
    except urllib.error.HTTPError as e:
        errors += 1
        err_body = e.read().decode('utf-8', errors='replace')
        print(f"  [{i+1:2d}/{len(chunks)}] ERROR {e.code}: {chunk['id']} — {err_body[:120]}")
    except Exception as e:
        errors += 1
        print(f"  [{i+1:2d}/{len(chunks)}] ERROR: {chunk['id']} — {e}")

    time.sleep(0.15)

print()
print("=" * 50)
print(f"Загружено успешно: {success}")
print(f"Ошибок:           {errors}")
print("=" * 50)
if errors == 0:
    print("Все чанки загружены в Supabase!")
