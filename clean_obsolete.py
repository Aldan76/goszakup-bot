"""
clean_obsolete.py — Очищает чанки от строк с «Исключен», «утратил силу», «Сноска.»
и перезаписывает JSON + обновляет Supabase.

Правило: при каждом добавлении нового документа запускать эту чистку.
"""
import sys
import json
import re
import urllib.request
import urllib.error
import os
import time

sys.stdout.reconfigure(encoding='utf-8')

BASE = r"C:\Users\fazyl\Documents\Project1\goszakup-bot"

# Загружаем .env
env = {}
with open(os.path.join(BASE, '.env'), encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

SUPABASE_URL = env['SUPABASE_URL']
SUPABASE_KEY = env['SUPABASE_KEY']

# ─── Паттерны строк для удаления ──────────────────────────────────────────────
# Строки, которые целиком удаляем (не весь чанк, только эту строку)
LINE_DELETE_PATTERNS = re.compile(
    r'исключ[её]н\b.*?(?:приказ|постановление|закон)'  # "Исключен приказом..."
    r'|утратил[аи]?\s+силу'                             # "утратил силу"
    r'|признан[аы]?\s+утратив'                         # "признан утратившим силу"
    r'|^сноска\.\s+'                                    # "Сноска. Пункт X – в редакции..."
    r'|^примечание\.\s+приложение\s+\d+\s*[-–]',       # "Примечание. Приложение N - в редакции"
    re.IGNORECASE
)

FILES = [
    (f"{BASE}\\data\\chunks_zakon.json",    "Закон"),
    (f"{BASE}\\data\\chunks_pravila.json",  "Правила №678"),
    (f"{BASE}\\data\\chunks_reestrov.json", "Правила реестров №646"),
    (f"{BASE}\\data\\chunks_ktp.json",      "Правила КТП №327"),
    (f"{BASE}\\data\\chunks_dvc.json",      "Методика ДВЦ №260"),
]


def clean_chunk_text(text: str) -> tuple[str, int]:
    """
    Удаляет из текста строки с устаревшими нормами.
    Возвращает (очищенный текст, кол-во удалённых строк).
    """
    lines = text.split('\n')
    cleaned = []
    removed = 0
    for line in lines:
        if LINE_DELETE_PATTERNS.search(line.strip()):
            removed += 1
        else:
            cleaned.append(line)
    return '\n'.join(cleaned).strip(), removed


def update_supabase(chunk_id: str, new_text: str, new_char_count: int):
    """Обновляет текст чанка в Supabase через PATCH."""
    body = json.dumps({
        "text": new_text,
        "char_count": new_char_count,
    }).encode('utf-8')

    url = f"{SUPABASE_URL}/rest/v1/chunks?id=eq.{urllib.request.quote(chunk_id)}"
    req = urllib.request.Request(
        url,
        data=body,
        method='PATCH',
        headers={
            'Content-Type': 'application/json',
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer': 'return=minimal',
        }
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status


def main():
    print("=" * 60)
    print("Чистка устаревших норм из базы знаний")
    print("=" * 60)

    total_chunks_cleaned = 0
    total_lines_removed = 0

    for fpath, label in FILES:
        with open(fpath, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        print(f"\n--- {label} ({len(chunks)} чанков) ---")
        changed = False

        for c in chunks:
            original_text = c['text']
            new_text, removed = clean_chunk_text(original_text)

            if removed > 0:
                c['text'] = new_text
                c['char_count'] = len(new_text)
                total_chunks_cleaned += 1
                total_lines_removed += removed
                changed = True

                title = (c.get('article_title') or c.get('chapter', ''))[:55]
                print(f"  ОЧИЩЕНО [{c['id']}] {title}")
                print(f"    Удалено строк: {removed}")

                # Обновляем Supabase
                try:
                    status = update_supabase(c['id'], new_text, c['char_count'])
                    print(f"    Supabase: HTTP {status} OK")
                except Exception as e:
                    print(f"    Supabase ERROR: {e}")

                time.sleep(0.15)

        if not changed:
            print("  OK — нечего чистить")
        else:
            # Перезаписываем JSON
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            print(f"  JSON обновлён: {fpath.split(chr(92))[-1]}")

    print(f"\n{'='*60}")
    print(f"ИТОГО:")
    print(f"  Чанков очищено: {total_chunks_cleaned}")
    print(f"  Строк удалено:  {total_lines_removed}")
    print('='*60)
    if total_chunks_cleaned == 0:
        print("Все чанки чистые — ничего не требовалось удалять.")
    else:
        print("Чистка завершена. Supabase и JSON обновлены.")


if __name__ == '__main__':
    main()
