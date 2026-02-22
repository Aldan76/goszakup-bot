"""
upload_civil_code.py — Загружает чанки ГК РК в Supabase.

Запуск:
    python upload_civil_code.py

Читает data/chunks_civil_code.json, загружает в таблицу chunks
с source_platform='civil_code'.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(override=True)

from supabase import create_client

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]
client = create_client(url, key)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_FILE = os.path.join(BASE_DIR, "data", "chunks_civil_code.json")


def main():
    if not os.path.exists(CHUNKS_FILE):
        print(f"Файл не найден: {CHUNKS_FILE}")
        sys.exit(1)

    with open(CHUNKS_FILE, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Загружаю {len(chunks)} чанков ГК РК в Supabase...")
    print(f"Supabase URL: {url}")

    success = errors = 0

    for i, chunk in enumerate(chunks):
        # Разбираем metadata
        try:
            meta = json.loads(chunk.get("metadata", "{}"))
        except Exception:
            meta = {}

        row = {
            "id":              chunk["id"],
            "document_short":  "ГК РК",
            "document_name":   meta.get("source", "Гражданский кодекс РК"),
            "source_type":     "law",
            "source_platform": "civil_code",
            "chapter":         None,
            "chapter_num":     None,
            "article_num":     meta.get("article_num"),
            "article_title":   chunk.get("article_title"),
            "punkt_range":     None,
            "text":            chunk["content"],
            "official_url":    chunk.get("article_url", "https://adilet.zan.kz"),
            "char_count":      len(chunk["content"]),
        }

        try:
            client.table("chunks").upsert(row).execute()
            success += 1
            title = (chunk.get("article_title") or "")[:50]
            print(f"  [{i+1:3d}/{len(chunks)}] OK  {chunk['id'][:55]}")
        except Exception as e:
            errors += 1
            print(f"  [{i+1:3d}/{len(chunks)}] ERR {chunk['id'][:40]} - {e}")

        time.sleep(0.05)

    print(f"\n{'='*55}")
    print(f"ИТОГО: загружено {success}, ошибок {errors}")
    if errors == 0:
        print("Vse chunki GK zagruzheny!")
        print("Sleduyuschiy shag: obnovit rag.py")
    else:
        print(f"Есть ошибки: {errors} чанков не загружено")


if __name__ == "__main__":
    main()
