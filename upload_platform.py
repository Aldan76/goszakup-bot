"""
upload_platform.py — Загружает чанки инструкций площадок в Supabase.

Запуск:
    python upload_platform.py --platform goszakup
    python upload_platform.py --platform omarket
    python upload_platform.py --platform all   # оба сразу

Требования:
    pip install supabase python-dotenv
"""

import argparse
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


def upload_platform(platform: str):
    chunks_path = os.path.join(BASE_DIR, "data", f"chunks_{platform}.json")
    if not os.path.exists(chunks_path):
        print(f"  ⚠ Файл не найден: {chunks_path}")
        return 0, 0

    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"\nПлатформа: {platform} — {len(chunks)} чанков")
    print(f"Подключаемся к Supabase: {url}")

    success = errors = 0

    for i, chunk in enumerate(chunks):
        row = {
            "id":              chunk["id"],
            "document_short":  chunk["document_short"],
            "document_name":   chunk["document_name"],
            "source_type":     chunk.get("source_type", "instruction"),
            "source_platform": chunk.get("source_platform", platform),
            "chapter":         chunk.get("chapter"),
            "chapter_num":     chunk.get("chapter_num"),
            "article_num":     chunk.get("article_num"),
            "article_title":   chunk.get("article_title"),
            "punkt_range":     chunk.get("punkt_range"),
            "text":            chunk["text"],
            "official_url":    chunk["official_url"],
            "char_count":      chunk.get("char_count", len(chunk["text"])),
        }

        try:
            client.table("chunks").upsert(row).execute()
            success += 1
            title = (chunk.get("article_title") or chunk.get("chapter", ""))[:50]
            print(f"  [{i+1:3d}/{len(chunks)}] OK {chunk['id'][:50]}")
        except Exception as e:
            errors += 1
            print(f"  [{i+1:3d}/{len(chunks)}] ERR: {chunk['id']} - {e}")

        time.sleep(0.05)

    print(f"\n{'='*50}")
    print(f"  {platform}: успешно {success}, ошибок {errors}")
    return success, errors


def main():
    parser = argparse.ArgumentParser(description="Загрузка инструкций площадок в Supabase")
    parser.add_argument("--platform", choices=["goszakup", "omarket", "tax", "all"],
                        default="all", help="Какую платформу загружать")
    args = parser.parse_args()

    platforms = ["goszakup", "omarket", "tax"] if args.platform == "all" else [args.platform]

    total_ok = total_err = 0
    for p in platforms:
        ok, err = upload_platform(p)
        total_ok += ok
        total_err += err

    print(f"\n{'='*50}")
    print(f"ИТОГО: загружено {total_ok}, ошибок {total_err}")
    if total_err == 0:
        print("OK Vse chunki zagruzheny!")


if __name__ == "__main__":
    main()
