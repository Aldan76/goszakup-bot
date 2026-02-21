"""
check_obsolete.py — Ищет в чанках упоминания «утратил силу» и похожих фраз.
Показывает найденные чанки и конкретные строки.
"""
import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

BASE = r"C:\Users\fazyl\Documents\Project1\goszakup-bot\data"

FILES = [
    (f"{BASE}\\chunks_zakon.json",    "Закон"),
    (f"{BASE}\\chunks_pravila.json",  "Правила №678"),
    (f"{BASE}\\chunks_reestrov.json", "Правила реестров №646"),
]

# Фразы-маркеры устаревших норм
OBSOLETE_PATTERNS = re.compile(
    r'утратил[аи]?\s+силу'
    r'|признан[аы]?\s+утратив'
    r'|исключ[её]н[аы]?\b'
    r'|не\s+применяется'
    r'|в\s+редакции\s+.*?признан',
    re.IGNORECASE
)

total_bad_chunks = 0
total_bad_lines = 0

for fpath, label in FILES:
    with open(fpath, 'r', encoding='utf-8') as f:
        chunks = json.load(f)

    print(f"\n{'='*60}")
    print(f"{label} ({len(chunks)} чанков): {fpath.split(chr(92))[-1]}")
    print('='*60)

    found_in_file = 0
    for c in chunks:
        text = c.get('text', '')
        lines = text.split('\n')
        bad_lines = [l.strip() for l in lines if OBSOLETE_PATTERNS.search(l)]

        if bad_lines:
            found_in_file += 1
            total_bad_chunks += 1
            total_bad_lines += len(bad_lines)
            chunk_id = c['id']
            title = (c.get('article_title') or c.get('chapter', ''))[:60]
            print(f"\n  Чанк: [{chunk_id}] {title}")
            print(f"  Строк с «утратил силу»: {len(bad_lines)}")
            for bl in bad_lines[:5]:
                print(f"    >> {bl[:130]}")
            if len(bad_lines) > 5:
                print(f"    ... и ещё {len(bad_lines) - 5} строк")

    if found_in_file == 0:
        print("  OK — утративших силу норм не найдено")
    else:
        print(f"\n  Итого чанков с проблемами: {found_in_file}")

print(f"\n{'='*60}")
print(f"ИТОГО по всем документам:")
print(f"  Чанков с устаревшими нормами: {total_bad_chunks}")
print(f"  Строк к удалению:             {total_bad_lines}")
print('='*60)
