"""
parse_reestrov.py — Парсер HTML документа Правила реестров №646 (V2400035143)
и загрузчик чанков в Supabase.

Запуск:
    python parse_reestrov.py
"""

import json
import os
import re
import sys
import html as html_module
import time

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HTML_PATH = os.path.join(DATA_DIR, "raw_Pravila_reestrov_646.html")

DOC_META = {
    "document_short": "Правила реестров",
    "document_name": "Правила формирования и ведения реестров в сфере государственных закупок, Приказ МФ РК от 2024 №646",
    "source_type": "rules",
    "base_url": "https://adilet.zan.kz/rus/docs/V2400035143",
}


def strip_tags(text: str) -> str:
    """Удаляет HTML теги и декодирует HTML-entities."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_main_content(html: str) -> str:
    """Извлекает основной текст документа из HTML страницы adilet.zan.kz."""
    # Ищем блок с классом document или article_body или doctext
    patterns = [
        r'<div[^>]+id=["\']?docBody["\']?[^>]*>(.*?)</div\s*>(?=\s*<div)',
        r'<div[^>]+class=["\'][^"\']*docBody[^"\']*["\'][^>]*>(.*?)</div\s*>\s*(?=<div[^>]+class=["\'][^"\']*footer)',
        r'<div[^>]+class=["\'][^"\']*article_body[^"\']*["\'][^>]*>(.*)',
        r'<div[^>]+class=["\'][^"\']*content_text[^"\']*["\'][^>]*>(.*)',
    ]
    for p in patterns:
        m = re.search(p, html, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1)

    # Если не нашли — ищем по якорям z1, z2... это начало текста документа
    # Ищем от первого <a name="z1"> до </body>
    m = re.search(r'(<a\s+name=["\']?z1["\']?\s*/?>.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)

    # Последний вариант: весь body
    m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)

    return html


def parse_html_to_paragraphs(html: str) -> list[str]:
    """
    Преобразует HTML документа в список параграфов.
    Ориентируется на структуру adilet.zan.kz.
    """
    # Ищем все блоки <p>, <div class="paragraf">, строки с пунктами
    # На adilet.zan.kz каждый пункт обёрнут в <p> или <div>

    # Разбиваем по тегам p, div, h2, h3
    # Удаляем скрипты и стили
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)

    # Разбиваем по блочным тегам
    parts = re.split(r'<(?:p|div|h[1-6]|li|tr|td|br)\b[^>]*>', html, flags=re.IGNORECASE)

    paragraphs = []
    for part in parts:
        text = strip_tags(part)
        if len(text) > 5:
            paragraphs.append(text)

    return paragraphs


def clean_text(text: str) -> str:
    """Нормализует пробелы."""
    text = re.sub(r'\u00a0', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# Регулярки для структуры документа
RE_CHAPTER = re.compile(r'^Глава\s+(\d+)[.\s]*(.*)', re.IGNORECASE)
RE_SECTION = re.compile(r'^(?:Раздел|РАЗДЕЛ)\s+(\d+[\w.-]*)[.\s]*(.*)')
RE_PUNKT   = re.compile(r'^(\d{1,3})\.\s+\S')
RE_APPENDIX = re.compile(r'^Приложение\s+(\d+[\w-]*)[.\s]*(.*)', re.IGNORECASE)

MAX_PUNKTS_PER_CHUNK = 15


def parse_reestrov(paragraphs: list[str]) -> list[dict]:
    """
    Разбивает Правила реестров на чанки по главам/разделам.
    Приложения 1–4,7,10 добавляем (реестры/перечни), бланки (5,6,8) и «к приказу» — пропускаем.
    """
    chunks = []
    current_chapter_num = 0
    current_chapter_title = ""
    current_lines = []
    current_punkt_nums = []
    in_content = False

    # Счётчик для уникальных ID приложений
    pril_counter = {}

    # Приложения-бланки — не нужны боту (только шаблоны писем/бланки)
    SKIP_PRIL = {"5", "6", "8"}
    # Приложения-реестры — нужны
    USEFUL_PRIL = {"1", "2", "3", "4", "7", "10"}

    current_pril_num = None
    current_pril_skip = False

    def flush_chapter(lines, punkt_nums, ch_num, ch_title, chunk_idx=0):
        text = clean_text('\n'.join(lines))
        if not text or len(text) < 30:
            return
        first_p = punkt_nums[0] if punkt_nums else 0
        last_p  = punkt_nums[-1] if punkt_nums else 0
        suffix  = f"_part{chunk_idx}" if chunk_idx > 0 else ""
        # Безопасный ID
        safe_num = re.sub(r'[^\w]', '_', str(ch_num))
        chunk_id = f"reestrov_gl{safe_num}{suffix}"
        # Уникальность ID
        if chunk_id in pril_counter:
            pril_counter[chunk_id] += 1
            chunk_id = f"{chunk_id}_v{pril_counter[chunk_id]}"
        else:
            pril_counter[chunk_id] = 0

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
        # Начало документа — ищем первую Главу
        if not in_content:
            if RE_CHAPTER.match(para) or RE_SECTION.match(para):
                in_content = True
            else:
                continue

        m_chapter  = RE_CHAPTER.match(para)
        m_punkt    = RE_PUNKT.match(para)
        m_appendix = RE_APPENDIX.match(para)

        if m_appendix:
            # Сохраняем текущий блок
            if current_lines and not current_pril_skip:
                if isinstance(current_chapter_num, int):
                    split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
                else:
                    flush_chapter(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title, 0)
            current_lines = []
            current_punkt_nums = []

            pril_raw = m_appendix.group(1).strip()
            pril_title_raw = m_appendix.group(2).strip()

            # Пропускаем "к приказу" и бланки
            if "приказу" in para.lower() or "приказ" in pril_title_raw.lower():
                current_pril_skip = True
                continue

            if pril_raw in SKIP_PRIL:
                current_pril_skip = True
                continue

            current_pril_skip = False
            current_pril_num = pril_raw
            current_chapter_num = f"Прил{pril_raw}"
            # Название возьмём из следующих строк (после заголовка)
            current_chapter_title = pril_title_raw or f"Приложение {pril_raw}"
            current_lines = [para]
            current_punkt_nums = []
            continue

        # Если мы в пропускаемом приложении
        if current_pril_skip:
            # Проверяем не началась ли следующая Глава
            if m_chapter:
                current_pril_skip = False
                # падаем ниже на обработку главы
            else:
                continue

        if m_chapter:
            if current_lines:
                split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
            current_chapter_num = int(m_chapter.group(1))
            current_chapter_title = m_chapter.group(2).strip()
            current_pril_num = None
            current_lines = [para]
            current_punkt_nums = []
        else:
            current_lines.append(para)
            if m_punkt:
                current_punkt_nums.append(int(m_punkt.group(1)))

    # Финализируем последний блок
    if current_lines and not current_pril_skip:
        if isinstance(current_chapter_num, int):
            split_and_flush(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title)
        else:
            flush_chapter(current_lines, current_punkt_nums, current_chapter_num, current_chapter_title, 0)

    return chunks


def main():
    print("=" * 60)
    print("Парсинг: Правила реестров №646 (V2400035143)")
    print("=" * 60)

    # Читаем HTML
    with open(HTML_PATH, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()
    print(f"HTML загружен: {len(html):,} символов")

    # Извлекаем основной контент
    main_content = extract_main_content(html)
    print(f"Основной контент: {len(main_content):,} символов")

    # Парсим параграфы
    paragraphs = parse_html_to_paragraphs(main_content)
    print(f"Параграфов извлечено: {len(paragraphs)}")

    # Показываем первые 20 параграфов для проверки структуры
    print("\n--- Первые 20 параграфов (для проверки) ---")
    for i, p in enumerate(paragraphs[:20]):
        print(f"  [{i:2d}] {p[:100]}")

    # Ищем главы
    print("\n--- Найденные главы ---")
    for p in paragraphs:
        if RE_CHAPTER.match(p):
            print(f"  ГЛАВА: {p[:80]}")
        elif RE_APPENDIX.match(p):
            print(f"  ПРИЛ:  {p[:80]}")

    # Парсим чанки
    chunks = parse_reestrov(paragraphs)
    print(f"\nЧанков создано: {len(chunks)}")

    for c in chunks:
        print(f"  [{c['id']}] {c['article_title'][:70]}  ({c['char_count']} симв.)")

    # Сохраняем
    out_path = os.path.join(DATA_DIR, "chunks_reestrov.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено: {out_path}")

    return chunks


if __name__ == '__main__':
    main()
