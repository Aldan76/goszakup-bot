"""
upload_chunks.py — Загружает все чанки из chunks_all.json в Supabase.

Запуск:
    python upload_chunks.py

Требования:
    pip install supabase python-dotenv
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(override=True)

from supabase import create_client

# ─── Подключение ──────────────────────────────────────────────────────────────

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]
client = create_client(url, key)

# ─── Загрузка чанков ──────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
chunks_path = os.path.join(BASE_DIR, "data", "chunks_all.json")

with open(chunks_path, encoding="utf-8") as f:
    chunks = json.load(f)

print(f"Загружено чанков из файла: {len(chunks)}")
print(f"Подключаемся к Supabase: {url}")

# ─── Загрузка в Supabase ──────────────────────────────────────────────────────

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

    try:
        # upsert — если уже есть, обновит
        client.table("chunks").upsert(row).execute()
        success += 1
        title = (chunk.get("article_title") or chunk.get("chapter", ""))[:50]
        print(f"  [{i+1:2d}/{len(chunks)}] OK: {chunk['id']} — {title}")
    except Exception as e:
        errors += 1
        print(f"  [{i+1:2d}/{len(chunks)}] ERROR: {chunk['id']} — {e}")

    # Небольшая пауза чтобы не перегружать API
    time.sleep(0.1)

print(f"\n{'='*50}")
print(f"Загружено успешно: {success}")
print(f"Ошибок:           {errors}")
print(f"{'='*50}")

if errors == 0:
    print("Все чанки загружены! Supabase готов к работе.")
else:
    print("Есть ошибки — проверь вывод выше.")
