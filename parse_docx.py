"""
parse_docx.py — Парсер .docx файлов для RAG-бота по госзакупкам РК.

Запуск:
    python parse_docx.py

Результат:
    data/chunks_zakon.json    — чанки из Закона (по статьям)
    data/chunks_pravila.json  — чанки из Правил (по главам)
    data/chunks_all.json      — объединённый файл

Требования:
    pip install python-docx lxml
"""

import json
import re
import os
from docx import Document

# ─── Пути к файлам ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(os.path.dirname(BASE_DIR), "documents")
DATA_DIR = os.path.join(BASE_DIR, "data")

ZAKON_PATH   = os.path.join(DOCS_DIR, "Zakon.docx")
PRAVILA_PATH = os.path.join(DOCS_DIR, "Pravila.docx")  # полный файл с приложениями

os.makedirs(DATA_DIR, exist_ok=True)


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def table_to_text(table) -> str:
    """Преобразует таблицу docx в читаемый текст."""
    lines = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        # убираем пустые и дублирующиеся ячейки (merged cells дублируют текст)
        seen = set()
        unique = []
        for c in cells:
            if c and c not in seen:
                seen.add(c)
                unique.append(c)
        if unique:
            lines.append(" | ".join(unique))
    return "\n".join(lines)


def extract_content_from_docx(path: str) -> list[str]:
    """
    Извлекает параграфы И содержимое таблиц из .docx файла
    в правильном порядке (как они идут в документе).
    """
    doc = Document(path)
    items = []

    # python-docx хранит параграфы и таблицы раздельно,
    # но в XML они идут в порядке документа через doc.element.body
    from docx.oxml.ns import qn

    for child in doc.element.body:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

        if tag == 'p':
            # параграф
            text = ''.join(r.text for r in child.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if r.text)
            text = text.strip()
            if text:
                items.append(text)

        elif tag == 'tbl':
            # таблица — найдём её объект и преобразуем
            # ищем таблицу по её xml элементу
            for tbl in doc.tables:
                if tbl._tbl is child:
                    ttext = table_to_text(tbl)
                    if ttext.strip():
                        items.append(f"[ТАБЛИЦА]\n{ttext}\n[/ТАБЛИЦА]")
                    break

    return items


def clean_text(text: str) -> str:
    """Нормализует пробелы и спецсимволы."""
    text = re.sub(r'\u00a0', ' ', text)          # неразрывный пробел
    text = re.sub(r'[ \t]+', ' ', text)           # множественные пробелы
    text = re.sub(r'\n{3,}', '\n\n', text)        # тройные переносы
    return text.strip()


# ─── Парсер Закона ────────────────────────────────────────────────────────────

ZAKON_META = {
    "document_short": "Закон о госзакупках",
    "document_name": "Закон РК «О государственных закупках» от 01.07.2024 № 106-VIII ЗРК",
    "source_type": "law",
    "base_url": "https://adilet.zan.kz/rus/docs/Z2400000106",
}

RE_CHAPTER = re.compile(r'^Глава\s+(\d+)[.\s]*(.*)', re.IGNORECASE)
RE_ARTICLE = re.compile(r'^Статья\s+(\d+)[.\s]*(.*)', re.IGNORECASE)


def parse_zakon(paragraphs: list[str]) -> list[dict]:
    """Разбивает Закон на чанки по статьям."""
    chunks = []
    current_chapter_num = 0
    current_chapter_title = ""
    current_article_num = None
    current_article_title = ""
    current_lines = []

    def flush_article():
        if current_article_num is None:
            return
        text = clean_text('\n'.join(current_lines))
        if not text:
            return
        chunk = {
            "id": f"zakon_st{current_article_num}",
            "document_short": ZAKON_META["document_short"],
            "document_name": ZAKON_META["document_name"],
            "source_type": ZAKON_META["source_type"],
            "chapter": f"Глава {current_chapter_num}. {current_chapter_title}".strip('. '),
            "chapter_num": current_chapter_num,
            "article_num": current_article_num,
            "article_title": current_article_title,
            "punkt_range": None,
            "text": text,
            "official_url": f"{ZAKON_META['base_url']}#st{current_article_num}",
            "char_count": len(text),
        }
        chunks.append(chunk)

    for para in paragraphs:
        m_chapter = RE_CHAPTER.match(para)
        m_article = RE_ARTICLE.match(para)

        if m_chapter:
            current_chapter_num = int(m_chapter.group(1))
            current_chapter_title = m_chapter.group(2).strip()

        elif m_article:
            flush_article()
            current_article_num = int(m_article.group(1))
            current_article_title = para
            current_lines = [para]

        else:
            if current_article_num is not None:
                current_lines.append(para)

    flush_article()
    return chunks


# ─── Парсер Правил ────────────────────────────────────────────────────────────

PRAVILA_META = {
    "document_short": "Правила госзакупок",
    "document_name": "Правила осуществления государственных закупок, Приказ МФ РК от 09.10.2024 № 687",
    "source_type": "rules",
    "base_url": "https://adilet.zan.kz/rus/docs/V2400035238",
}

RE_PRA_CHAPTER   = re.compile(r'^Глава\s+(\d+)[.\s]*(.*)', re.IGNORECASE)
RE_PRA_PUNKT     = re.compile(r'^(\d{1,4})\.\s+\S')
RE_PRA_PRILOZHENIE = re.compile(r'^Приложение\s+(\d+[\w-]*)[.\s]*(.*)', re.IGNORECASE)
# Таблица-заголовок приложения: "[ТАБЛИЦА]\nПриложение N\n..."
RE_PRA_PRIL_NOTE = re.compile(r'^Примечание\.\s+Приложение\s+(\d+)', re.IGNORECASE)
# Приложение внутри [ТАБЛИЦА] блока
RE_PRA_PRIL_TABLE = re.compile(r'\[ТАБЛИЦА\]\s*\nПриложение\s+(\d+[\w-]*)\s*\n(.*)', re.IGNORECASE | re.DOTALL)

MAX_PUNKTS_PER_CHUNK = 20
# Последний пункт основных Правил — после него идут приложения
LAST_MAIN_PUNKT = 600


def parse_pravila(paragraphs: list[str]) -> list[dict]:
    """
    Разбивает Правила на чанки:
    - Главы 1-19: по главам (с разбивкой если глава большая)
    - Приложения: каждое приложение как отдельный чанк (только заголовок + первые пункты)
    """
    chunks = []

    current_chapter_num = 0
    current_chapter_title = ""
    current_lines = []
    current_punkt_nums = []

    # Состояние парсера
    in_main_rules = False       # парсим основные главы
    in_prilozhenie = False      # парсим приложения
    main_rules_done = False     # основные правила закончились (пункт 600+)
    current_pril_num = ""
    current_pril_title = ""
    current_pril_lines = []
    pril_line_count = 0
    MAX_PRIL_LINES = 80         # берём первые 80 строк каждого приложения

    def flush_chapter(lines, punkt_nums, chapter_num, chapter_title, chunk_idx=0):
        text = clean_text('\n'.join(lines))
        if not text:
            return
        first_p = punkt_nums[0] if punkt_nums else 0
        last_p  = punkt_nums[-1] if punkt_nums else 0
        suffix  = f"_part{chunk_idx}" if chunk_idx > 0 else ""
        chunk_id = f"pravila_gl{chapter_num}{suffix}"
        chunk = {
            "id": chunk_id,
            "document_short": PRAVILA_META["document_short"],
            "document_name": PRAVILA_META["document_name"],
            "source_type": PRAVILA_META["source_type"],
            "chapter": f"Глава {chapter_num}. {chapter_title}".strip('. '),
            "chapter_num": chapter_num,
            "article_num": None,
            "article_title": (
                f"Глава {chapter_num}. {chapter_title} — Пункты {first_p}–{last_p}"
                if punkt_nums else f"Глава {chapter_num}. {chapter_title}"
            ),
            "punkt_range": [first_p, last_p] if punkt_nums else None,
            "text": text,
            "official_url": PRAVILA_META["base_url"],
            "char_count": len(text),
        }
        chunks.append(chunk)

    def split_and_flush(lines, punkt_nums, chapter_num, chapter_title):
        if not punkt_nums or len(punkt_nums) <= MAX_PUNKTS_PER_CHUNK:
            flush_chapter(lines, punkt_nums, chapter_num, chapter_title, chunk_idx=0)
            return
        punkt_line_indices = []
        for i, line in enumerate(lines):
            m = RE_PRA_PUNKT.match(line)
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
            flush_chapter(part_lines, part_nums, chapter_num, chapter_title, chunk_idx=part_idx)
            part_idx += 1

    def flush_prilozhenie():
        if not current_pril_lines:
            return
        text = clean_text('\n'.join(current_pril_lines))
        if not text or len(text) < 20:
            return
        # Нормализуем номер для ID (убираем спецсимволы)
        pril_id_num = re.sub(r'[^\w]', '_', str(current_pril_num))
        chunk = {
            "id": f"pravila_pril{pril_id_num}",
            "document_short": PRAVILA_META["document_short"],
            "document_name": PRAVILA_META["document_name"],
            "source_type": PRAVILA_META["source_type"],
            "chapter": f"Приложение {current_pril_num}",
            "chapter_num": None,
            "article_num": None,
            "article_title": f"Приложение {current_pril_num}. {current_pril_title}".strip('. '),
            "punkt_range": None,
            "text": text,
            "official_url": PRAVILA_META["base_url"],
            "char_count": len(text),
        }
        chunks.append(chunk)

    for para in paragraphs:
        # Активируем парсинг при первой Главе основных Правил
        if not in_main_rules and not in_prilozhenie:
            if RE_PRA_CHAPTER.match(para):
                in_main_rules = True
            else:
                continue

        m_chapter     = RE_PRA_CHAPTER.match(para)
        m_punkt       = RE_PRA_PUNKT.match(para)
        m_prilozhenie = RE_PRA_PRILOZHENIE.match(para)
        m_pril_note   = RE_PRA_PRIL_NOTE.match(para)
        m_pril_table  = RE_PRA_PRIL_TABLE.search(para)  # приложение в таблице-заголовке

        # Детектируем конец основных Правил:
        # Вариант 1: "Примечание. Приложение N - в редакции..."
        # Вариант 2: пункт > LAST_MAIN_PUNKT (600) — следующий параграф после него
        if in_main_rules and not main_rules_done:
            # Проверяем: встретили таблицу-заголовок Приложения
            if m_pril_table:
                if current_lines:
                    split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
                    current_lines = []
                    current_punkt_nums = []
                main_rules_done = True
                in_main_rules = False
                in_prilozhenie = True
                current_pril_num = m_pril_table.group(1).strip()
                current_pril_title = m_pril_table.group(2).strip()[:100]
                current_pril_lines = [para]
                pril_line_count = 1
                continue
            # Проверяем: встретили примечание об изменении приложения
            if m_pril_note:
                if current_lines:
                    split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
                    current_lines = []
                    current_punkt_nums = []
                main_rules_done = True
                in_main_rules = False
                in_prilozhenie = True
                current_pril_num = m_pril_note.group(1)
                current_pril_title = para
                current_pril_lines = [para]
                pril_line_count = 1
                continue
            # Проверяем: пункт превысил LAST_MAIN_PUNKT
            if m_punkt:
                pnum = int(m_punkt.group(1))
                if pnum > LAST_MAIN_PUNKT:
                    if current_lines:
                        split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
                        current_lines = []
                        current_punkt_nums = []
                    main_rules_done = True
                    in_main_rules = False
                    continue  # этот параграф пропускаем

        # ── Приложение ────────────────────────────────────────────
        if m_prilozhenie and not in_main_rules:
            # Сохраняем предыдущую главу или приложение
            if in_main_rules and current_lines:
                split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
                current_lines = []
                current_punkt_nums = []
                in_main_rules = False

            if in_prilozhenie:
                flush_prilozhenie()

            in_prilozhenie = True
            current_pril_num = m_prilozhenie.group(1).strip()
            current_pril_title = m_prilozhenie.group(2).strip()
            current_pril_lines = [para]
            pril_line_count = 1
            continue

        # ── Если мы внутри Приложения ─────────────────────────────
        if in_prilozhenie:
            # Новый заголовок приложения в таблице
            if m_pril_table:
                flush_prilozhenie()
                current_pril_num = m_pril_table.group(1).strip()
                current_pril_title = m_pril_table.group(2).strip()[:100]
                current_pril_lines = [para]
                pril_line_count = 1
            elif m_pril_note:
                flush_prilozhenie()
                current_pril_num = m_pril_note.group(1)
                current_pril_title = para
                current_pril_lines = [para]
                pril_line_count = 1
            elif pril_line_count < MAX_PRIL_LINES:
                current_pril_lines.append(para)
                pril_line_count += 1
            continue

        # ── Основные Главы Правил ─────────────────────────────────
        if m_chapter and not main_rules_done:
            if current_lines:
                split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
            current_chapter_num = int(m_chapter.group(1))
            current_chapter_title = m_chapter.group(2).strip()
            current_lines = [para]
            current_punkt_nums = []

        else:
            if not main_rules_done:
                current_lines.append(para)
                if m_punkt:
                    current_punkt_nums.append(int(m_punkt.group(1)))

    # Финализируем последнюю главу или приложение
    if in_main_rules and current_lines:
        split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
    if in_prilozhenie:
        flush_prilozhenie()

    return chunks


# ─── Основная функция ─────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Парсер документов госзакупок РК")
    print("=" * 60)

    # ── Закон ──────────────────────────────────────────────────
    print(f"\n[1/2] Читаем Закон: {ZAKON_PATH}")
    zakon_items = extract_content_from_docx(ZAKON_PATH)
    print(f"      Элементов (параграфы+таблицы): {len(zakon_items)}")

    zakon_chunks = parse_zakon(zakon_items)
    print(f"      Чанков (статей): {len(zakon_chunks)}")

    zakon_path = os.path.join(DATA_DIR, "chunks_zakon.json")
    with open(zakon_path, 'w', encoding='utf-8') as f:
        json.dump(zakon_chunks, f, ensure_ascii=False, indent=2)
    print(f"      Сохранено: {zakon_path}")

    # ── Правила ────────────────────────────────────────────────
    print(f"\n[2/2] Читаем Правила: {PRAVILA_PATH}")
    pravila_items = extract_content_from_docx(PRAVILA_PATH)
    print(f"      Элементов (параграфы+таблицы): {len(pravila_items)}")

    pravila_chunks = parse_pravila(pravila_items)
    chapters_count = sum(1 for c in pravila_chunks if c['id'].startswith('pravila_gl'))
    prils_count    = sum(1 for c in pravila_chunks if c['id'].startswith('pravila_pril'))
    print(f"      Чанков глав: {chapters_count}, приложений: {prils_count}, итого: {len(pravila_chunks)}")

    pravila_path = os.path.join(DATA_DIR, "chunks_pravila.json")
    with open(pravila_path, 'w', encoding='utf-8') as f:
        json.dump(pravila_chunks, f, ensure_ascii=False, indent=2)
    print(f"      Сохранено: {pravila_path}")

    # ── Объединённый файл ──────────────────────────────────────
    all_chunks = zakon_chunks + pravila_chunks
    all_path = os.path.join(DATA_DIR, "chunks_all.json")
    with open(all_path, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # ── Статистика ─────────────────────────────────────────────
    total_chars = sum(c['char_count'] for c in all_chunks)
    est_tokens  = int(total_chars / 3.5)

    print(f"\n{'=' * 60}")
    print(f"ИТОГО:")
    print(f"  Чанков Закона:   {len(zakon_chunks)}")
    print(f"  Чанков Правил:   {len(pravila_chunks)}  (глав: {chapters_count}, приложений: {prils_count})")
    print(f"  Всего чанков:    {len(all_chunks)}")
    print(f"  Всего символов:  {total_chars:,}")
    print(f"  ~Токенов (оцен): {est_tokens:,}")
    print(f"  Сохранено:       {all_path}")
    print(f"{'=' * 60}")

    if est_tokens > 180_000:
        print("ВНИМАНИЕ: контекст может превысить 200k токенов Claude.")
    else:
        print("OK: Укладывается в контекстное окно Claude (200k токенов).")

    # ── Превью ─────────────────────────────────────────────────
    print(f"\n--- Первые 3 чанка Закона ---")
    for c in zakon_chunks[:3]:
        print(f"  [{c['id']}] {c['article_title'][:60]}  ({c['char_count']} симв.)")

    print(f"\n--- Первые 3 чанка Правил (главы) ---")
    for c in [x for x in pravila_chunks if x['id'].startswith('pravila_gl')][:3]:
        print(f"  [{c['id']}] {c['article_title'][:60]}  ({c['char_count']} симв.)")

    print(f"\n--- Первые 3 приложения ---")
    for c in [x for x in pravila_chunks if x['id'].startswith('pravila_pril')][:3]:
        print(f"  [{c['id']}] {c['article_title'][:60]}  ({c['char_count']} симв.)")


if __name__ == '__main__':
    main()
