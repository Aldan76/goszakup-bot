"""
build_anchor_map.py
Builds correct punkt->z_anchor and article->z_anchor maps from adilet.zan.kz,
then updates chunks_all.json and Supabase with correct URLs.
"""

import json
import os
import re
import ssl
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "data", "chunks_all.json")
MAP_PATH = os.path.join(BASE_DIR, "data", "anchor_map.json")

ZAKON_URL   = "https://adilet.zan.kz/rus/docs/Z2400000106"
PRAVILA_URL = "https://adilet.zan.kz/rus/docs/V2400035238"
ZAKON_BASE  = "https://adilet.zan.kz/rus/docs/Z2400000106"
PRAVILA_BASE = "https://adilet.zan.kz/rus/docs/V2400035238"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def fetch_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=CTX, timeout=40) as r:
        raw = r.read()
    # Decode as UTF-8 (site declared charset) - preserves Cyrillic correctly
    return raw.decode("utf-8", errors="replace")


def extract_anchor_blocks(content):
    """Returns list of (z_id, text_after_anchor) pairs."""
    pattern = re.compile(
        r'(?:id|name)="(z\d+)"[^>]*>([\s\S]{0,800}?)(?=(?:id|name)="z\d+")',
        re.DOTALL
    )
    return pattern.findall(content)


def clean_text(html_block):
    text = re.sub(r'<[^>]+>', ' ', html_block)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def build_pravila_map(content):
    """punkt_number -> z_anchor for Pravila."""
    blocks = extract_anchor_blocks(content)
    punkt_to_z = {}

    for z_id, html_block in blocks:
        text = clean_text(html_block)
        # Match "NNN. Capital letter" - paragraph start
        m = re.search(r'(?<!\d)(\d{1,3})\.\s+[А-ЯЁA-Z\u04b0\u04b1]', text)
        if m:
            pnum = int(m.group(1))
            if pnum not in punkt_to_z:
                punkt_to_z[pnum] = z_id

    return punkt_to_z


def build_zakon_map(content):
    """article_number -> z_anchor for Zakon.

    On adilet.zan.kz, Zakon articles use <a name="zN"> anchors (not id=).
    Each name-anchor is placed just before the article title text.
    We find all name anchors and check the next 300 chars for 'Статья N'.
    """
    STATYA = '\u0421\u0442\u0430\u0442\u044c\u044f'  # Статья in UTF-8

    article_to_z = {}
    name_anchors = list(re.finditer(r'<a\s+name="(z\d+)"\s*>', content))

    for m in name_anchors:
        z_id = m.group(1)
        after = content[m.end(): m.end() + 300]
        art_m = re.search(STATYA + r'\s+(\d+)', after)
        if art_m:
            art_num = int(art_m.group(1))
            if art_num not in article_to_z:
                article_to_z[art_num] = z_id

    return article_to_z


def save_maps(zakon_map, pravila_map):
    data = {
        "zakon_article_to_z": {str(k): v for k, v in sorted(zakon_map.items())},
        "pravila_punkt_to_z": {str(k): v for k, v in sorted(pravila_map.items())},
    }
    with open(MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Saved anchor map: {MAP_PATH}")
    print(f"     Zakon articles:  {len(zakon_map)}")
    print(f"     Pravila punkts:  {len(pravila_map)}")
    return data


def get_zakon_url(article_num, zakon_map):
    z = zakon_map.get(article_num) or zakon_map.get(str(article_num))
    if z:
        return f"{ZAKON_BASE}#{z}"
    return ZAKON_BASE


def get_pravila_url(punkt_range, chunk_id, pravila_map):
    if "pril" in chunk_id:
        return PRAVILA_BASE
    if punkt_range and isinstance(punkt_range, list):
        first = punkt_range[0]
        z = pravila_map.get(first) or pravila_map.get(str(first))
        if z:
            return f"{PRAVILA_BASE}#{z}"
    return PRAVILA_BASE


def update_json(zakon_map, pravila_map):
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    updated = 0
    for chunk in chunks:
        src = chunk.get("source_type")
        if src == "law":
            art = chunk.get("article_num")
            if art:
                new_url = get_zakon_url(art, zakon_map)
                if new_url != chunk.get("official_url"):
                    chunk["official_url"] = new_url
                    updated += 1
        elif src == "rules":
            new_url = get_pravila_url(chunk.get("punkt_range"), chunk.get("id", ""), pravila_map)
            if new_url != chunk.get("official_url"):
                chunk["official_url"] = new_url
                updated += 1

    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"[OK] JSON updated: {updated} chunks got correct anchor URLs")
    return chunks


def update_supabase(chunks):
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        print("[ERR] Missing SUPABASE_URL or SUPABASE_KEY")
        return

    to_update = [c for c in chunks if c.get("source_type") in ("law", "rules")]
    print(f"\nUpdating {len(to_update)} chunks in Supabase...")

    ok = errors = 0
    for chunk in to_update:
        cid = chunk["id"]
        url = chunk["official_url"]
        payload = json.dumps({"official_url": url}).encode("utf-8")
        req = urllib.request.Request(
            f"{supabase_url}/rest/v1/chunks?id=eq.{cid}",
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
                    print(f"  [WARN] [{cid}] status {resp.status}")
                    errors += 1
        except urllib.error.HTTPError as e:
            print(f"  [ERR] [{cid}] HTTP {e.code}: {e.read().decode()[:80]}")
            errors += 1
        except Exception as e:
            print(f"  [ERR] [{cid}] {e}")
            errors += 1

    print("=" * 50)
    print(f"[OK] Success: {ok}/{len(to_update)}")
    if errors:
        print(f"[ERR] Errors: {errors}")


def preview(chunks):
    print("\n[PREVIEW] Sample URLs after update:")
    shown = 0
    for c in chunks:
        if c.get("source_type") in ("law", "rules") and shown < 12:
            print(f"  [{c['id']}] -> {c['official_url']}")
            shown += 1


if __name__ == "__main__":
    print("Fetching Zakon page...")
    zakon_content = fetch_page(ZAKON_URL)
    print(f"  size: {len(zakon_content)} chars")

    print("Fetching Pravila page...")
    pravila_content = fetch_page(PRAVILA_URL)
    print(f"  size: {len(pravila_content)} chars")

    print("\nBuilding anchor maps...")
    zakon_map   = build_zakon_map(zakon_content)
    pravila_map = build_pravila_map(pravila_content)

    save_maps(zakon_map, pravila_map)

    # Show key examples
    print("\n[ZAKON] Article -> anchor:")
    for art in [1, 5, 9, 16, 28, 29]:
        z = zakon_map.get(art, "NOT FOUND")
        print(f"  Statya {art} -> #{z} -> {ZAKON_BASE}#{z}")

    print("\n[PRAVILA] Punkt -> anchor:")
    for p in [3, 5, 25, 46, 114, 212, 275, 394]:
        z = pravila_map.get(p, "NOT FOUND")
        print(f"  Punkt {p} -> #{z} -> {PRAVILA_BASE}#{z}")

    chunks = update_json(zakon_map, pravila_map)
    preview(chunks)
    update_supabase(chunks)
