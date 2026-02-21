"""
parse_dvc.py — Парсер HTML Единой методики расчёта ДВЦ №260 (V1800016942)
и загрузчик чанков в Supabase.

Документ не имеет «Глав» — структура:
  - Пункты 1–8: общие положения
  - Раздел 1 «Расчет ДВЦ в договоре на поставку товаров» (пункты описания + формулы)
  - Раздел 2 «Расчет ДВЦ в договоре на выполнение работы/услуги» (кроме недропользования)
  - Раздел 3 «ДВЦ в договоре на работы по недропользованию»
  - Раздел 4 «ДВЦ в договоре на работы/услуги по недропользованию»
  - Раздел 5 «ДВЦ в закупках заказчика за отчётный период»
  - Приложения (формы отчётности)

Стратегия чанкинга: разбиваем по смысловым разделам.
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
HTML_PATH = os.path.join(DATA_DIR, "raw_Metodika_DVC_260.html")

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
    "document_short": "Методика ДВЦ",
    "document_name": "Единая методика расчета организациями внутристрановой ценности (ДВЦ) при закупке товаров, работ и услуг, Приказ от 20.04.2018 №260",
    "source_type": "rules",
    "base_url": "https://adilet.zan.kz/rus/docs/V1800016942",
}

# Паттерны строк для удаления (устаревшие нормы)
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
    return [strip_tags(p) for p in parts if len(strip_tags(p)) > 5]


def clean_text(text: str) -> str:
    text = re.sub(r'\u00a0', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def clean_obsolete_lines(text: str) -> tuple[str, int]:
    lines = text.split('\n')
    cleaned, removed = [], 0
    for line in lines:
        if LINE_DELETE_PATTERNS.search(line.strip()):
            removed += 1
        else:
            cleaned.append(line)
    return '\n'.join(cleaned).strip(), removed


# Паттерны структуры Методики ДВЦ
RE_PUNKT     = re.compile(r'^(\d{1,3})\.\s+\S')
RE_APPENDIX  = re.compile(r'^Приложение\b', re.IGNORECASE)
# Начало собственно Методики
RE_START     = re.compile(r'^1\.\s+Настоящая\s+Единая\s+методика', re.IGNORECASE)
# Подпункты алгоритма: «1) "Расчет..."», «2) "Расчет..."» и т.д.
RE_ALGO_ITEM = re.compile(r'^(\d+)\)\s+[«""]?(Расчет|Rj)', re.IGNORECASE)
# Заголовки таблиц (пропускаем)
RE_TABLE_HDR = re.compile(
    r'^(?:Форма,\s+предназначенная|'
    r'Периодичность\s+и\s+сроки|'
    r'Источники\s+информации|'
    r'Алгоритм\s+административного|'
    r'Определение\s+административного|'
    r'Наименование\s+административного)',
    re.IGNORECASE
)


def parse_dvc(paragraphs: list[str]) -> list[dict]:
    """
    Разбивает Методику ДВЦ на чанки:
    1. Общие положения (пункты 1–9, включая таблицу перечня показателей)
    2. Алгоритм 1: Расчет ДВЦ в договоре на поставку товаров
    3. Алгоритм 2: Расчет ДВЦ в договоре на работу/услугу (кроме недропользования)
    4. Алгоритм 3: Rj — доля ФОТ казахстанских кадров
    5. Алгоритм 4: Расчет ДВЦ для контрактов по недропользованию
    6. Алгоритм 5: Расчет ДВЦ в закупках заказчика за отчётный период
    Приложения (перечни утративших силу приказов) — пропускаем.
    """
    chunks = []
    id_counter = {}

    def make_id(base: str) -> str:
        if base not in id_counter:
            id_counter[base] = 0
            return base
        id_counter[base] += 1
        return f"{base}_v{id_counter[base]}"

    def save_chunk(lines: list[str], chunk_id: str, title: str, punkt_nums: list[int]):
        raw = '\n'.join(lines)
        text, removed = clean_obsolete_lines(raw)
        text = clean_text(text)
        if not text or len(text) < 50:
            return
        if removed:
            print(f"    [чистка] удалено {removed} устаревших строк из {chunk_id}")
        first_p = punkt_nums[0] if punkt_nums else 0
        last_p  = punkt_nums[-1] if punkt_nums else 0
        uid = make_id(chunk_id)
        chunk = {
            "id": uid,
            "document_short": DOC_META["document_short"],
            "document_name":  DOC_META["document_name"],
            "source_type":    DOC_META["source_type"],
            "chapter":        title,
            "chapter_num":    None,
            "article_num":    None,
            "article_title":  (
                f"{title} — Пункты {first_p}–{last_p}" if punkt_nums else title
            ),
            "punkt_range":    [first_p, last_p] if punkt_nums else None,
            "text":           text,
            "official_url":   DOC_META["base_url"],
            "char_count":     len(text),
        }
        chunks.append(chunk)

    in_content    = False
    in_appendix   = False
    current_lines = []
    current_punks = []
    current_title = "Общие положения и перечень показателей ДВЦ"
    current_id    = "dvc_obshchie"
    section_num   = 0

    # Заголовки алгоритмов — строим при обнаружении «N) "Расчет..."»
    ALGO_TITLES = {
        "1": "Алгоритм расчёта ДВЦ в договоре на поставку товаров",
        "2": "Алгоритм расчёта ДВЦ в договоре на выполнение работы или оказание услуги (кроме недропользования)",
        "3": "Алгоритм расчёта Rj — доля ФОТ казахстанских кадров",
        "4": "Алгоритм расчёта ДВЦ в договоре на работы или услуги по контрактам недропользования",
        "5": "Алгоритм расчёта ДВЦ в закупках заказчика за отчётный период",
    }

    for para in paragraphs:
        if not in_content:
            if RE_START.match(para):
                in_content = True
            else:
                continue

        if in_appendix:
            continue

        # Приложение к приказу — всё что после него пропускаем
        if RE_APPENDIX.match(para):
            if current_lines:
                save_chunk(current_lines, current_id, current_title, current_punks)
                current_lines, current_punks = [], []
            in_appendix = True
            continue

        # Детектируем начало нового алгоритма: «1) "Расчет внутристрановой...»
        m_algo = RE_ALGO_ITEM.match(para)
        if m_algo:
            algo_num = m_algo.group(1)
            if current_lines:
                save_chunk(current_lines, current_id, current_title, current_punks)
                current_lines, current_punks = [], []
            section_num += 1
            current_title = ALGO_TITLES.get(algo_num, f"Алгоритм {algo_num}")
            current_id    = f"dvc_algo{algo_num}"
            current_lines = [para]
            current_punks = []
            continue

        # Пропускаем строки-заголовки таблиц (они не несут смысловой нагрузки)
        if RE_TABLE_HDR.match(para):
            continue

        current_lines.append(para)
        m = RE_PUNKT.match(para)
        if m:
            try:
                current_punks.append(int(m.group(1)))
            except ValueError:
                pass

    if current_lines and not in_appendix:
        save_chunk(current_lines, current_id, current_title, current_punks)

    return chunks


def upload_to_supabase(chunks: list[dict]):
    print(f"\nЗагружаем {len(chunks)} чанков в Supabase...")
    success, errors = 0, 0
    for i, chunk in enumerate(chunks):
        row = {k: chunk.get(k) for k in [
            "id", "document_short", "document_name", "source_type",
            "chapter", "chapter_num", "article_num", "article_title",
            "punkt_range", "text", "official_url", "char_count"
        ]}
        body = json.dumps(row).encode('utf-8')
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/chunks",
            data=body, method='POST',
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
                title = (chunk.get("article_title") or "")[:55]
                print(f"  [{i+1:2d}/{len(chunks)}] OK: {chunk['id']} — {title}")
        except urllib.error.HTTPError as e:
            errors += 1
            print(f"  [{i+1:2d}/{len(chunks)}] ERROR {e.code}: {chunk['id']} — {e.read().decode()[:100]}")
        except Exception as e:
            errors += 1
            print(f"  [{i+1:2d}/{len(chunks)}] ERROR: {chunk['id']} — {e}")
        time.sleep(0.15)
    print(f"\nЗагружено: {success}, Ошибок: {errors}")
    return errors == 0


def main():
    print("=" * 60)
    print("Парсинг: Методика ДВЦ №260 (V1800016942)")
    print("=" * 60)

    with open(HTML_PATH, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()
    print(f"HTML загружен: {len(html):,} символов")

    paragraphs = parse_html_to_paragraphs(html)
    print(f"Параграфов: {len(paragraphs)}")

    chunks = parse_dvc(paragraphs)
    print(f"\nЧанков создано: {len(chunks)}")
    for c in chunks:
        print(f"  [{c['id']}] {c['article_title'][:70]}  ({c['char_count']} симв.)")

    out_path = os.path.join(DATA_DIR, "chunks_dvc.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено: {out_path}")

    ok = upload_to_supabase(chunks)
    if ok:
        print("\nВсе чанки загружены в Supabase!")
    else:
        print("\nЕсть ошибки!")

    return chunks


if __name__ == '__main__':
    main()
