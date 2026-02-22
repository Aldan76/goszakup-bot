"""
parse_platform.py — Парсер инструкций с площадок goszakup.gov.kz и omarket.kz.

Режимы работы:
  1. Из сохранённого HTML-файла:
       python parse_platform.py --file data/raw_goszakup_help.html --platform goszakup
  2. Из текстового файла (скопированный текст страницы):
       python parse_platform.py --txt data/goszakup_help.txt --platform goszakup
  3. Интерактивный — вводите URL + текст вручную:
       python parse_platform.py --interactive --platform omarket

Результат сохраняется в data/chunks_goszakup.json или data/chunks_omarket.json
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

# ─── Настройки площадок ───────────────────────────────────────────────────────

PLATFORM_META = {
    "goszakup": {
        "document_short": "Инструкция goszakup.gov.kz",
        "document_name":  "Инструкция по работе с порталом государственных закупок goszakup.gov.kz",
        "source_type":    "instruction",
        "source_platform": "goszakup",
        "base_url":       "https://www.goszakup.gov.kz",
    },
    "omarket": {
        "document_short": "Инструкция omarket.kz",
        "document_name":  "Инструкция по работе с электронным магазином omarket.kz",
        "source_type":    "instruction",
        "source_platform": "omarket",
        "base_url":       "https://www.omarket.kz",
    },
}

CHUNK_SIZE = 1500   # символов
CHUNK_OVERLAP = 200 # пересечение между чанками


# ─── Очистка текста ───────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Убирает лишние пробелы, множественные переносы и мусор."""
    # Убираем множественные пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Убираем пробелы в начале строк
    text = re.sub(r'^[ \t]+', '', text, flags=re.MULTILINE)
    # Убираем пробелы в конце строк
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    # Убираем повторяющиеся пробелы
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


# ─── Разбивка на чанки ────────────────────────────────────────────────────────

def split_into_chunks(text: str, url: str, section_title: str,
                      meta: dict, chunk_size: int = CHUNK_SIZE,
                      overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """
    Разбивает текст на чанки с учётом абзацев.
    Старается не разрывать абзацы посередине.
    """
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > chunk_size and current:
            # Сохраняем текущий чанк
            chunks.append('\n\n'.join(current))
            # Оставляем последний абзац как перекрытие
            overlap_paras = []
            overlap_len = 0
            for p in reversed(current):
                if overlap_len + len(p) <= overlap:
                    overlap_paras.insert(0, p)
                    overlap_len += len(p)
                else:
                    break
            current = overlap_paras
            current_len = overlap_len
        current.append(para)
        current_len += para_len

    if current:
        chunks.append('\n\n'.join(current))

    # Формируем объекты чанков
    platform = meta["source_platform"]
    # Slug: ASCII-часть заголовка + хеш для гарантии уникальности
    ascii_slug = re.sub(r'[^a-z0-9]+', '_', section_title.lower())[:20].strip('_')
    title_hash = hashlib.md5(section_title.encode('utf-8')).hexdigest()[:8]
    slug = f"{ascii_slug}_{title_hash}" if ascii_slug else title_hash
    timestamp = datetime.now().strftime("%Y%m%d")

    result = []
    for i, chunk_text in enumerate(chunks):
        if len(chunk_text.strip()) < 50:
            continue  # пропускаем слишком короткие
        chunk_id = f"{platform}_{slug}_{timestamp}_{i+1:03d}"
        result.append({
            "id":              chunk_id,
            "document_short":  meta["document_short"],
            "document_name":   meta["document_name"],
            "source_type":     meta["source_type"],
            "source_platform": meta["source_platform"],
            "chapter":         section_title,
            "chapter_num":     None,
            "article_num":     None,
            "article_title":   section_title,
            "punkt_range":     None,
            "text":            chunk_text.strip(),
            "official_url":    url,
            "char_count":      len(chunk_text),
        })
    return result


# ─── Парсинг HTML ─────────────────────────────────────────────────────────────

def parse_html_file(filepath: str, url: str, platform: str) -> list[dict]:
    """Парсит сохранённый HTML-файл."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("Установите: pip install beautifulsoup4 lxml")
        sys.exit(1)

    meta = PLATFORM_META[platform]

    with open(filepath, encoding="utf-8", errors="replace") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")

    # Убираем ненужные теги
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "iframe", "noscript", "form"]):
        tag.decompose()

    all_chunks = []

    # Ищем заголовки H1-H3 как границы секций
    headings = soup.find_all(['h1', 'h2', 'h3'])

    if headings:
        for heading in headings:
            section_title = clean_text(heading.get_text())
            if len(section_title) < 3:
                continue

            # Собираем текст до следующего заголовка того же или выше уровня
            content_parts = [section_title]
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h1', 'h2', 'h3']:
                    break
                txt = sibling.get_text(separator='\n')
                if txt.strip():
                    content_parts.append(clean_text(txt))

            full_text = '\n\n'.join(content_parts)
            if len(full_text) > 100:
                chunks = split_into_chunks(full_text, url, section_title, meta)
                all_chunks.extend(chunks)
    else:
        # Нет заголовков — берём весь текст страницы
        main = soup.find('main') or soup.find('article') or soup.find('body')
        if main:
            text = clean_text(main.get_text(separator='\n'))
            title = soup.title.get_text() if soup.title else "Инструкция"
            all_chunks.extend(split_into_chunks(text, url, title, meta))

    print(f"  HTML → {len(all_chunks)} чанков из {filepath}")
    return all_chunks


# ─── Парсинг TXT (скопированный текст) ───────────────────────────────────────

def parse_txt_file(filepath: str, url: str, platform: str) -> list[dict]:
    """
    Парсит текстовый файл — текст, скопированный со страницы.
    Поддерживает два формата:
    1. Структурированный: === СТРАНИЦА: <title> === ... === КОНЕЦ ===
    2. Обычный: определяет секции по строкам в ВЕРХНЕМ РЕГИСТРЕ или начинающимся с цифры+точки
    """
    meta = PLATFORM_META[platform]

    with open(filepath, encoding="utf-8", errors="replace") as f:
        raw = f.read()

    text = clean_text(raw)

    # Проверяем, есть ли структурированный формат
    page_pattern = re.compile(
        r'===\s*СТРАНИЦА:\s*(.+?)\s*===\s*(.*?)\s*===\s*КОНЕЦ\s*===',
        re.DOTALL | re.IGNORECASE
    )
    structured_sections = page_pattern.findall(text)

    if structured_sections:
        # Структурированный формат: каждая страница — отдельная секция
        all_chunks = []
        for page_title, page_content in structured_sections:
            page_title = page_title.strip()
            # Извлекаем URL из первой строки контента если есть
            page_url = url
            url_match = re.match(r'URL:\s*(https?://\S+)', page_content.strip())
            if url_match:
                page_url = url_match.group(1)
                page_content = page_content[url_match.end():].strip()

            if len(page_content) < 50:
                continue
            chunks = split_into_chunks(page_content, page_url, page_title, meta)
            all_chunks.extend(chunks)

        print(f"  TXT -> {len(structured_sections)} sektsiy -> {len(all_chunks)} chunks iz {filepath}")
        return all_chunks

    # Обычный формат: определяем заголовки по паттернам
    lines = text.split('\n')

    def is_heading(line: str) -> bool:
        line = line.strip()
        if not line or len(line) > 120:
            return False
        if re.match(r'^\d+[\.\d]*\s+\S', line):
            return True
        if line.isupper() and len(line) > 3:
            return True
        if re.match(r'^(Шаг|Step|Раздел|Глава|Часть)\s+', line, re.IGNORECASE):
            return True
        return False

    sections = []
    current_title = "Общая информация"
    current_lines = []

    for line in lines:
        if is_heading(line):
            if current_lines:
                sections.append((current_title, '\n'.join(current_lines)))
            current_title = line.strip()
            current_lines = [line.strip()]
        else:
            if line.strip():
                current_lines.append(line.strip())

    if current_lines:
        sections.append((current_title, '\n'.join(current_lines)))

    all_chunks = []
    for title, content in sections:
        if len(content) < 50:
            continue
        chunks = split_into_chunks(content, url, title, meta)
        all_chunks.extend(chunks)

    print(f"  TXT -> {len(sections)} sektsiy -> {len(all_chunks)} chunks iz {filepath}")
    return all_chunks


# ─── Интерактивный режим ──────────────────────────────────────────────────────

def interactive_mode(platform: str) -> list[dict]:
    """
    Интерактивный ввод: пользователь вводит URL и текст секции вручную.
    Удобно для копирования текста из браузера.
    """
    meta = PLATFORM_META[platform]
    all_chunks = []

    print(f"\n{'='*60}")
    print(f"Интерактивный режим — платформа: {platform}")
    print("Для каждой страницы введите URL и вставьте текст.")
    print("Введите 'ГОТОВО' на отдельной строке чтобы завершить секцию.")
    print("Введите 'ВЫХОД' чтобы закончить.")
    print('='*60)

    while True:
        url = input("\nURL страницы (или 'ВЫХОД'): ").strip()
        if url.upper() == 'ВЫХОД':
            break
        if not url:
            continue

        section = input("Название раздела (или Enter для авто): ").strip()
        if not section:
            section = url.split('/')[-1] or "Раздел"

        print("Вставьте текст страницы (завершите строкой 'ГОТОВО'):")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip().upper() == 'ГОТОВО':
                break
            lines.append(line)

        text = clean_text('\n'.join(lines))
        if len(text) < 50:
            print("  ⚠ Текст слишком короткий, пропускаю.")
            continue

        chunks = split_into_chunks(text, url, section, meta)
        all_chunks.extend(chunks)
        print(f"  ✓ Добавлено {len(chunks)} чанков для: {section}")

    return all_chunks


# ─── Сохранение результата ───────────────────────────────────────────────────

def save_chunks(chunks: list[dict], platform: str, output_path: str = None):
    if not chunks:
        print("Нет чанков для сохранения!")
        return

    if not output_path:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(base_dir, "data", f"chunks_{platform}.json")

    # Если файл уже существует — мержим, не дублируем
    existing = []
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
        existing_ids = {c["id"] for c in existing}
        new_chunks = [c for c in chunks if c["id"] not in existing_ids]
        all_chunks = existing + new_chunks
        print(f"  Существующих: {len(existing)}, новых: {len(new_chunks)}")
    else:
        all_chunks = chunks

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"\nOK Sokhraneno {len(all_chunks)} chunks -> {output_path}")
    return output_path


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Парсер инструкций площадок госзакупок")
    parser.add_argument("--platform", choices=["goszakup", "omarket"], required=True,
                        help="Площадка: goszakup или omarket")
    parser.add_argument("--file",   help="Путь к HTML-файлу")
    parser.add_argument("--txt",    help="Путь к TXT-файлу (скопированный текст)")
    parser.add_argument("--url",    help="URL страницы (для --file и --txt)")
    parser.add_argument("--interactive", action="store_true",
                        help="Интерактивный ввод текста")
    parser.add_argument("--output", help="Путь для сохранения JSON (по умолчанию data/chunks_PLATFORM.json)")
    args = parser.parse_args()

    chunks = []

    if args.file:
        url = args.url or PLATFORM_META[args.platform]["base_url"]
        chunks = parse_html_file(args.file, url, args.platform)
    elif args.txt:
        url = args.url or PLATFORM_META[args.platform]["base_url"]
        chunks = parse_txt_file(args.txt, url, args.platform)
    elif args.interactive:
        chunks = interactive_mode(args.platform)
    else:
        print("Укажите --file, --txt или --interactive")
        parser.print_help()
        sys.exit(1)

    if chunks:
        save_chunks(chunks, args.platform, args.output)
        print(f"\nСледующий шаг: python upload_platform.py --platform {args.platform}")
    else:
        print("Чанков не получено.")


if __name__ == "__main__":
    main()
