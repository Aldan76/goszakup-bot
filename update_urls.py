"""
update_urls.py -- Dobavlyaet yakornye ssylki (#p{N}) k chankam Pravil
v chunks_all.json i obnovlyaet ikh v Supabase.

Logika yakorey na adilet.zan.kz:
  Zakon:      #st{N}  -- uzhe est
  Pravila:    #p{N}   -- pervyy punkt diapazona, naprimer #p3, #p212
  Prilozhenie: bez yakoryay, bazovyy URL
"""

import json
import os
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "data", "chunks_all.json")

PRAVILA_BASE = "https://adilet.zan.kz/rus/docs/V2400035238"


def build_pravila_url(chunk):
    chunk_id = chunk.get("id", "")
    punkt_range = chunk.get("punkt_range")

    # Prilozhenia -- net yakorey, bazovyy URL
    if "pril" in chunk_id:
        return PRAVILA_BASE

    # Osnovnye glavy -- yakor na pervyy punkt
    if punkt_range and isinstance(punkt_range, list) and len(punkt_range) >= 1:
        first_punkt = punkt_range[0]
        return f"{PRAVILA_BASE}#p{first_punkt}"

    return PRAVILA_BASE


def update_json_file():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    updated = 0
    for chunk in chunks:
        if chunk.get("source_type") == "rules":
            new_url = build_pravila_url(chunk)
            if new_url != chunk.get("official_url"):
                chunk["official_url"] = new_url
                updated += 1

    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"[OK] JSON updated: {updated} Pravila chunks got anchor URLs")
    return chunks


def update_supabase(chunks):
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("[ERR] Missing SUPABASE_URL or SUPABASE_KEY in .env")
        return

    rules_chunks = [c for c in chunks if c.get("source_type") == "rules"]
    print(f"\nUpdating {len(rules_chunks)} Pravila chunks in Supabase...")

    ok = 0
    errors = 0

    for chunk in rules_chunks:
        chunk_id = chunk["id"]
        new_url = chunk["official_url"]

        payload = json.dumps({"official_url": new_url}).encode("utf-8")
        req = urllib.request.Request(
            f"{supabase_url}/rest/v1/chunks?id=eq.{chunk_id}",
            data=payload,
            method="PATCH",
            headers={
                "Content-Type": "application/json",
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Prefer": "return=minimal",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status in (200, 204):
                    ok += 1
                else:
                    print(f"  [WARN] [{chunk_id}] status {resp.status}")
                    errors += 1
        except urllib.error.HTTPError as e:
            print(f"  [ERR] [{chunk_id}] HTTP {e.code}: {e.read().decode()[:120]}")
            errors += 1
        except Exception as e:
            print(f"  [ERR] [{chunk_id}] {e}")
            errors += 1

    print("=" * 50)
    print(f"[OK] Success: {ok}/{len(rules_chunks)}")
    if errors:
        print(f"[ERR] Errors: {errors}")


def preview(chunks):
    print("\n[INFO] Sample anchor URLs:")
    rules = [c for c in chunks if c.get("source_type") == "rules"][:10]
    for c in rules:
        print(f"  [{c['id']}] punkt_range={c.get('punkt_range')} -> {c['official_url']}")


if __name__ == "__main__":
    chunks = update_json_file()
    preview(chunks)
    update_supabase(chunks)
