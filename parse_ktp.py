"""
parse_ktp.py — Парсер HTML документа Правила ведения реестра КТП №327 (V2500036717)
и загрузчик чанков в Supabase.

Запуск:
    python parse_ktp.py
"""

import json
import os
import re
import sys
import html as html_module
import time
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HTML_PATH = os.path.join(DATA_DIR, "raw_Pravila_KTP_327.html")

# Загружаем .env
env = {}
with open(os.path.join(BASE_DIR, '.env'), encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

SUPABASE_URL = env['SUPABASE_URL']
SUPABASE_KEY = env['SUPABASE_KEY']

DOC_META = {
    "document_short": "Правила КТП",
    "document_name": "Правила ведения реестра казахстанского содержания в товарах, работах, услугах (КТП), Приказ от 2025 №327",
    "source_type": "rules",
    "base_url": "https://adilet.zan.kz/rus/docs/V2500036717",
}

# ─── Паттерны строк для удаления (устаревшие нормы) ──────────────────────────
LINE_DELETE_PATTERNS = re.compile(
    r'исключ[её]н\b.*?(?:приказ|постановление|закон)'
    r'|утратил[аи]?\s+силу'
    r'|признан[аы]?\s+утратив'
    r'|^сноска\.\s+'
    r'|^примечание\.\s+приложение\s+\d+\s*[-–]',
    re.IGNORECASE
)


def strip_tags(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_html_to_paragraphs(html: str) -> list[str]:
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    parts = re.split(r'<(?:p|div|h[1-6]|li|tr|td|br)\b[^>]*>', html, flags=re.IGNORECASE)
    paragraphs = []
    for part in parts:
        text = strip_tags(part)
        if len(text) > 5:
            paragraphs.append(text)
    return paragraphs


def clean_text(text: str) -> str:
    text = re.sub(r'\u00a0', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def clean_obsolete_lines(text: str) -> tuple[str, int]:
    """Удаляет строки с устаревшими нормами. Возвращает (текст, кол-во удалённых строк)."""
    lines = text.split('\n')
    cleaned = []
    removed = 0
    for line in lines:
        if LINE_DELETE_PATTERNS.search(line.strip()):
            removed += 1
        else:
            cleaned.append(line)
    return '\n'.join(cleaned).strip(), removed


RE_CHAPTER  = re.compile(r'^Глава\s+(\d+)[.\s]*(.*)', re.IGNORECASE)
RE_SECTION  = re.compile(r'^(?:Раздел|РАЗДЕЛ)\s+(\d+[\w.-]*)[.\s]*(.*)')
RE_PUNKT    = re.compile(r'^(\d{1,3})\.\s+\S')
RE_APPENDIX = re.compile(r'^Приложение\s+(\d+[\w-]*)[.\s]*(.*)', re.IGNORECASE)

MAX_PUNKTS_PER_CHUNK = 15


def parse_ktp(paragraphs: list[str]) -> list[dict]:
    chunks = []
    current_chapter_num = 0
    current_chapter_title = ""
    current_lines = []
    current_punkt_nums = []
    in_content = False
    id_counter = {}

    current_pril_skip = False

    # Приложения-бланки — пропускаем (формы писем и т.п.)
    # Для КТП посмотрим что есть — пока берём все приложения
    SKIP_PRIL_KEYWORDS = ['бланк', 'форма письма', 'государственный герб']

    def make_unique_id(base_id: str) -> str:
        if base_id not in id_counter:
            id_counter[base_id] = 0
            return base_id
        else:
            id_counter[base_id] += 1
            return f"{base_id}_v{id_counter[base_id]}"

    def flush_chapter(lines, punkt_nums, ch_num, ch_title, chunk_idx=0):
        raw_text = '\n'.join(lines)
        text, removed = clean_obsolete_lines(raw_text)
        text = clean_text(text)
        if not text or len(text) < 30:
            return
        if removed > 0:
            print(f"    [чистка] удалено {removed} устаревших строк из чанка gl{ch_num}")
        first_p = punkt_nums[0] if punkt_nums else 0
        last_p  = punkt_nums[-1] if punkt_nums else 0
        suffix  = f"_part{chunk_idx}" if chunk_idx > 0 else ""
        safe_num = re.sub(r'[^\w]', '_', str(ch_num))
        chunk_id = make_unique_id(f"ktp_gl{safe_num}{suffix}")
        chunk = {
            "id": chunk_id,
            "document_short": DOC_META["document_short"],
            "document_name": DOC_META["document_name"],
            "source_type": DOC_META["source_type"],
            "chapter": f"Глава {ch_num}. {ch_title}".strip('. '),
            "chapter_num": ch_num if isinstance(ch_num, int) else None,
            "article_num": None,
            "article_title": (
                f"Глава {ch_num}. {ch_title} — Пункты {first_p}–{last_p}"
                if punkt_nums else f"Глава {ch_num}. {ch_title}"
            ).strip('. '),
            "punkt_range": [first_p, last_p] if punkt_nums else None,
            "text": text,
            "official_url": DOC_META["base_url"],
            "char_count": len(text),
        }
        chunks.append(chunk)

    def split_and_flush(lines, punkt_nums, ch_num, ch_title):
        if not punkt_nums or len(punkt_nums) <= MAX_PUNKTS_PER_CHUNK:
            flush_chapter(lines, punkt_nums, ch_num, ch_title, chunk_idx=0)
            return
        punkt_line_indices = []
        for i, line in enumerate(lines):
            m = RE_PUNKT.match(line)
            if m:
                punkt_line_indices.append((int(m.group(1)), i))
        part_idx = 0
        for start in range(0, len(punkt_line_indices), MAX_PUNKTS_PER_CHUNK):
            end = start + MAX_PUNKTS_PER_CHUNK
            part_punkts = punkt_line_indices[start:end]
            if not part_punkts:
                continue
            line_start = part_punkts[0][1]
            line_end = punkt_line_indices[end][1] if end < len(punkt_line_indices) else len(lines)
            part_lines = lines[line_start:line_end]
            part_nums  = [p[0] for p in part_punkts]
            flush_chapter(part_lines, part_nums, ch_num, ch_title, chunk_idx=part_idx)
            part_idx += 1

    for para in paragraphs:
        if not in_content:
            if RE_CHAPTER.match(para) or RE_SECTION.match(para):
                in_content = True
            else:
                continue

        m_chapter  = RE_CHAPTER.match(para)
        m_punkt    = RE_PUNKT.match(para)
        m_appendix = RE_APPENDIX.match(para)

        if m_appendix:
            if current_lines and not current_pril_skip:
                if isinstance(current_chapter_num, int):
                    split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
                else:
                    flush_chapter(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title, 0)
            current_lines = []
            current_punkt_nums = []

            pril_raw = m_appendix.group(1).strip()
            pril_title_raw = m_appendix.group(2).strip()

            # Пропускаем «к приказу»
            if "приказу" in para.lower():
                current_pril_skip = True
                continue

            # Проверяем — бланк или нет (по содержимому определим позже)
            current_pril_skip = False
            current_chapter_num = f"Прил{pril_raw}"
            current_chapter_title = pril_title_raw or f"Приложение {pril_raw}"
            current_lines = [para]
            current_punkt_nums = []
            continue

        if current_pril_skip:
            if m_chapter:
                current_pril_skip = False
            else:
                continue

        if m_chapter:
            if current_lines:
                split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
            current_chapter_num = int(m_chapter.group(1))
            current_chapter_title = m_chapter.group(2).strip()
            current_lines = [para]
            current_punkt_nums = []
        else:
            current_lines.append(para)
            if m_punkt:
                current_punkt_nums.append(int(m_punkt.group(1)))

    if current_lines and not current_pril_skip:
        if isinstance(current_chapter_num, int):
            split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
        else:
            flush_chapter(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title, 0)

    return chunks


def upload_to_supabase(chunks: list[dict]):
    print(f"\nЗагружаем {len(chunks)} чанков в Supabase...")
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
            url, data=body, method='POST',
            headers={
                'Content-Type': 'application/json',
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Prefer': 'resolution=merge-duplicates',
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

    print(f"\nЗагружено: {success}, Ошибок: {errors}")
    return errors == 0


def main():
    print("=" * 60)
    print("Парсинг: Правила КТП №327 (V2500036717)")
    print("=" * 60)

    with open(HTML_PATH, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()
    print(f"HTML загружен: {len(html):,} символов")

    paragraphs = parse_html_to_paragraphs(html)
    print(f"Параграфов извлечено: {len(paragraphs)}")

    # Показываем найденные главы для проверки структуры
    print("\n--- Найденные главы и приложения ---")
    for p in paragraphs:
        if RE_CHAPTER.match(p):
            print(f"  ГЛАВА: {p[:80]}")
        elif RE_APPENDIX.match(p):
            print(f"  ПРИЛ:  {p[:80]}")

    chunks = parse_ktp(paragraphs)
    print(f"\nЧанков создано: {len(chunks)}")
    for c in chunks:
        print(f"  [{c['id']}] {c['article_title'][:70]}  ({c['char_count']} симв.)")

    # Сохраняем JSON
    out_path = os.path.join(DATA_DIR, "chunks_ktp.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено: {out_path}")

    # Загружаем в Supabase
    ok = upload_to_supabase(chunks)
    if ok:
        print("\nВсе чанки загружены в Supabase!")
    else:
        print("\nЕсть ошибки — проверь вывод выше.")

    return chunks


if __name__ == '__main__':
    main()
