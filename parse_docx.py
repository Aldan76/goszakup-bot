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
PRAVILA_PATH = os.path.join(DOCS_DIR, "Pravila_bez_prilozhenye.docx")

os.makedirs(DATA_DIR, exist_ok=True)


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def extract_text_from_docx(path: str) -> list[str]:
    """Извлекает список параграфов из .docx файла."""
    doc = Document(path)
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return paragraphs


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

# Паттерны для Закона
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

    flush_article()  # последняя статья
    return chunks


# ─── Парсер Правил ────────────────────────────────────────────────────────────

PRAVILA_META = {
    "document_short": "Правила госзакупок",
    "document_name": "Правила осуществления государственных закупок, Приказ МФ РК от 09.10.2024 № 687",
    "source_type": "rules",
    "base_url": "https://adilet.zan.kz/rus/docs/V2400035238",
}

# Паттерны для Правил
RE_PRA_CHAPTER = re.compile(r'^Глава\s+(\d+)[.\s]*(.*)', re.IGNORECASE)
# Пункт начинается с цифры и точки в начале строки, например "3. " или "123. "
RE_PRA_PUNKT  = re.compile(r'^(\d{1,4})\.\s+\S')

# Размер чанка в Правилах: группируем пункты по главам
# Если глава слишком большая — разбиваем на блоки по MAX_PUNKTS пунктов
MAX_PUNKTS_PER_CHUNK = 20


def parse_pravila(paragraphs: list[str]) -> list[dict]:
    """Разбивает Правила на чанки по главам (с разбивкой если глава большая)."""
    chunks = []

    current_chapter_num = 0
    current_chapter_title = ""
    current_lines = []
    current_punkt_nums = []  # номера пунктов в текущем чанке

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
            "article_title": (f"Глава {chapter_num}. {chapter_title} — Пункты {first_p}–{last_p}" if punkt_nums else f"Глава {chapter_num}. {chapter_title}"),
            "punkt_range": [first_p, last_p],
            "text": text,
            "official_url": f"{PRAVILA_META['base_url']}",
            "char_count": len(text),
        }
        chunks.append(chunk)

    def split_and_flush(lines, punkt_nums, chapter_num, chapter_title):
        """Разбивает большую главу на части по MAX_PUNKTS пунктов."""
        if not punkt_nums or len(punkt_nums) <= MAX_PUNKTS_PER_CHUNK:
            flush_chapter(lines, punkt_nums, chapter_num, chapter_title, chunk_idx=0)
            return

        # Находим индексы строк где начинается каждый пункт
        punkt_line_indices = []  # (punkt_num, line_index)
        for i, line in enumerate(lines):
            m = RE_PRA_PUNKT.match(line)
            if m:
                punkt_line_indices.append((int(m.group(1)), i))

        # Разбиваем по MAX_PUNKTS пунктов
        part_idx = 0
        for start in range(0, len(punkt_line_indices), MAX_PUNKTS_PER_CHUNK):
            end = start + MAX_PUNKTS_PER_CHUNK
            part_punkts = punkt_line_indices[start:end]
            if not part_punkts:
                continue

            line_start = part_punkts[0][1]
            if end < len(punkt_line_indices):
                line_end = punkt_line_indices[end][1]
            else:
                line_end = len(lines)

            part_lines = lines[line_start:line_end]
            part_nums  = [p[0] for p in part_punkts]
            flush_chapter(part_lines, part_nums, chapter_num, chapter_title, chunk_idx=part_idx)
            part_idx += 1

    # Файл уже без приложений — начинаем парсить с первой "Глава 1"
    # Пропускаем вводную часть приказа (до первой Главы)
    in_main_rules = False

    for para in paragraphs:
        # Активируем парсинг как только встретили первую Главу
        if not in_main_rules:
            if RE_PRA_CHAPTER.match(para):
                in_main_rules = True
            else:
                continue

        m_chapter = RE_PRA_CHAPTER.match(para)
        m_punkt   = RE_PRA_PUNKT.match(para)

        if m_chapter:
            # Сохраняем предыдущую главу
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

    # Последняя глава
    if current_lines:
        split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)

    return chunks


# ─── Основная функция ─────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Парсер документов госзакупок РК")
    print("=" * 60)

    # ── Закон ──────────────────────────────────────────────────
    print(f"\n[1/2] Читаем Закон: {ZAKON_PATH}")
    zakon_paras = extract_text_from_docx(ZAKON_PATH)
    print(f"      Параграфов: {len(zakon_paras)}")

    zakon_chunks = parse_zakon(zakon_paras)
    print(f"      Чанков (статей): {len(zakon_chunks)}")

    zakon_path = os.path.join(DATA_DIR, "chunks_zakon.json")
    with open(zakon_path, 'w', encoding='utf-8') as f:
        json.dump(zakon_chunks, f, ensure_ascii=False, indent=2)
    print(f"      Сохранено: {zakon_path}")

    # ── Правила ────────────────────────────────────────────────
    print(f"\n[2/2] Читаем Правила: {PRAVILA_PATH}")
    pravila_paras = extract_text_from_docx(PRAVILA_PATH)
    print(f"      Параграфов: {len(pravila_paras)}")

    pravila_chunks = parse_pravila(pravila_paras)
    print(f"      Чанков (частей глав): {len(pravila_chunks)}")

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
    # Грубая оценка: 1 токен ≈ 3.5 символа для русского
    est_tokens = int(total_chars / 3.5)

    print(f"\n{'=' * 60}")
    print(f"ИТОГО:")
    print(f"  Чанков Закона:   {len(zakon_chunks)}")
    print(f"  Чанков Правил:   {len(pravila_chunks)}")
    print(f"  Всего чанков:    {len(all_chunks)}")
    print(f"  Всего символов:  {total_chars:,}")
    print(f"  ~Токенов (оцен): {est_tokens:,}")
    print(f"  Сохранено:       {all_path}")
    print(f"{'=' * 60}")

    if est_tokens > 180_000:
        print("ВНИМАНИЕ: контекст может превысить 200k токенов Claude.")
        print("Рассмотри разбивку на более мелкие чанки.")
    else:
        print("OK: Укладывается в контекстное окно Claude (200k токенов).")

    # ── Превью первых чанков ───────────────────────────────────
    print(f"\n--- Первые 3 чанка Закона ---")
    for c in zakon_chunks[:3]:
        print(f"  [{c['id']}] {c['article_title'][:60]}  ({c['char_count']} симв.)")

    print(f"\n--- Первые 3 чанка Правил ---")
    for c in pravila_chunks[:3]:
        print(f"  [{c['id']}] {c['article_title'][:60]}  ({c['char_count']} симв.)")


if __name__ == '__main__':
    main()
