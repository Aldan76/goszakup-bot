"""
parse_civil_code.py
Скачивает и парсит релевантные статьи ГК РК (Общая + Особенная часть)
с adilet.zan.kz на русском и казахском языках.
Использует только httpx (уже в requirements) и стандартную библиотеку.
Сохраняет чанки в data/chunks_civil_code.json
"""

import sys
import httpx
import hashlib
import json
import re
import time
import html

# Fix Windows cp1251 terminal encoding
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ─── Настройки ────────────────────────────────────────────────────────────────

SOURCES = [
    {
        "url": "https://adilet.zan.kz/rus/docs/K940001000_",
        "source": "Гражданский кодекс РК (Общая часть), русский язык",
        "lang": "ru",
        "part": "general",
        "article_re": re.compile(r"Статья\s+(\d+)"),
        "needed": set(list(range(147, 155)) +   # Сделки, форма, ЭЦП
                      list(range(268, 283)) +    # Понятие и исполнение обязательств
                      list(range(349, 361)) +    # Ответственность, неустойка
                      list(range(367, 378)) +    # Прекращение обязательств
                      list(range(378, 400))),    # Договор: оферта, акцепт
    },
    {
        "url": "https://adilet.zan.kz/rus/docs/K990000409_",
        "source": "Гражданский кодекс РК (Особенная часть), русский язык",
        "lang": "ru",
        "part": "special",
        "article_re": re.compile(r"Статья\s+(\d+)"),
        "needed": set(range(406, 478)),          # Купля-продажа, поставка
    },
    {
        "url": "https://adilet.zan.kz/kaz/docs/K940001000_",
        "source": "Азаматтық кодекс РК (Жалпы бөлім), қазақ тілі",
        "lang": "kz",
        "part": "general",
        "article_re": re.compile(r"(\d+)-б[аа]п"),
        "needed": set(list(range(147, 155)) +
                      list(range(268, 283)) +
                      list(range(349, 361)) +
                      list(range(367, 378)) +
                      list(range(378, 400))),
    },
    {
        "url": "https://adilet.zan.kz/kaz/docs/K990000409_",
        "source": "Азаматтық кодекс РК (Ерекше бөлім), қазақ тілі",
        "lang": "kz",
        "part": "special",
        "article_re": re.compile(r"(\d+)-б[аа]п"),
        "needed": set(range(406, 478)),
    },
]

DATE_SUFFIX = "20260222"
OUTPUT_FILE = "data/chunks_civil_code.json"
MAX_CHUNK_CHARS = 1500

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,kk;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# ─── Парсинг HTML без bs4 ─────────────────────────────────────────────────────

# H3 с id="z..." — заголовки статей
H3_RE = re.compile(
    r'<h3\s[^>]*id="(z\d+)"[^>]*>(.*?)<\/h3>',
    re.DOTALL | re.IGNORECASE
)
# P с id="z..." — абзацы в русской версии
P_ID_RE = re.compile(
    r'<p\s[^>]*id="(z\d+)"[^>]*>(.*?)<\/p>',
    re.DOTALL | re.IGNORECASE
)
# P без id — абзацы в казахской версии
P_ANY_RE = re.compile(
    r'<p(?:\s[^>]*)?>(.+?)<\/p>',
    re.DOTALL | re.IGNORECASE
)
TAG_STRIP_RE = re.compile(r'<[^>]+>')


def clean_text(raw):
    """Убирает HTML-теги и декодирует entities."""
    text = TAG_STRIP_RE.sub(' ', raw)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def fetch_articles(src):
    """Скачивает страницу и извлекает нужные статьи."""
    print(f"  Загружаю: {src['url']}")
    resp = httpx.get(src["url"], headers=HEADERS, timeout=60, follow_redirects=True, verify=False)
    page = resp.text

    article_re = src["article_re"]
    needed = src["needed"]

    # Определяем: используем p с id (ru) или p без id (kz)
    use_p_id = src["lang"] == "ru"

    # Собираем список всех элементов в порядке появления в документе
    # Каждый элемент: (position, type, inner_html)
    elements = []

    for m in H3_RE.finditer(page):
        elements.append((m.start(), "h3", m.group(2)))

    if use_p_id:
        for m in P_ID_RE.finditer(page):
            elements.append((m.start(), "p", m.group(2)))
    else:
        for m in P_ANY_RE.finditer(page):
            elements.append((m.start(), "p", m.group(1)))

    # Сортируем по позиции в документе
    elements.sort(key=lambda x: x[0])

    result = []
    in_article = False
    current_title = ""
    current_text = []
    current_num = 0

    for pos, tag, inner in elements:
        text = clean_text(inner)
        if not text:
            continue

        if tag == "h3":
            # Сохраняем предыдущую статью если нужна
            if in_article and current_num in needed and current_text:
                result.append({
                    "num": current_num,
                    "title": current_title,
                    "text": "\n".join(current_text),
                })
            am = article_re.search(text)
            if am:
                current_num = int(am.group(1))
                current_title = text
                current_text = []
                in_article = True
            else:
                in_article = False

        elif tag == "p" and in_article:
            if text:
                current_text.append(text)

    # Последняя статья
    if in_article and current_num in needed and current_text:
        result.append({
            "num": current_num,
            "title": current_title,
            "text": "\n".join(current_text),
        })

    print(f"  -> Найдено статей: {len(result)}")
    if len(result) == 0:
        all_h3 = [(clean_text(inner)) for _, tag, inner in elements if tag == 'h3']
        print(f"  ДИАГНОСТИКА: всего H3: {len(all_h3)}")
        for t in all_h3[:5]:
            print(f"    {t[:80]}")
    return result


# ─── Нарезка на чанки ─────────────────────────────────────────────────────────

def make_chunks(articles, src):
    chunks = []
    lang = src["lang"]
    part = src["part"]
    url = src["url"]
    source_label = src["source"]

    for art in articles:
        num = art["num"]
        title = art["title"]
        text = art["text"]

        if not text.strip():
            continue

        title_hash = hashlib.md5(f"{lang}_{part}_{num}".encode()).hexdigest()[:8]

        if len(text) <= MAX_CHUNK_CHARS:
            chunks.append({
                "id": f"civil_{lang}_{part}_{title_hash}_{DATE_SUFFIX}_001",
                "article_title": title,
                "article_url": url,
                "content": f"{title}\n\n{text}",
                "source_platform": "civil_code",
                "metadata": json.dumps({
                    "article_num": num,
                    "lang": lang,
                    "part": part,
                    "source": source_label,
                }, ensure_ascii=False),
            })
        else:
            # Разбиваем длинные статьи по абзацам
            paragraphs = text.split("\n")
            part_num = 1
            current = []
            current_len = 0

            for para in paragraphs:
                if current_len + len(para) > MAX_CHUNK_CHARS and current:
                    cid = f"civil_{lang}_{part}_{title_hash}_{DATE_SUFFIX}_{part_num:03d}"
                    chunks.append({
                        "id": cid,
                        "article_title": title,
                        "article_url": url,
                        "content": f"{title} (часть {part_num})\n\n" + "\n".join(current),
                        "source_platform": "civil_code",
                        "metadata": json.dumps({
                            "article_num": num,
                            "lang": lang,
                            "part": part,
                            "source": source_label,
                        }, ensure_ascii=False),
                    })
                    part_num += 1
                    current = [para]
                    current_len = len(para)
                else:
                    current.append(para)
                    current_len += len(para)

            if current:
                cid = f"civil_{lang}_{part}_{title_hash}_{DATE_SUFFIX}_{part_num:03d}"
                chunks.append({
                    "id": cid,
                    "article_title": title,
                    "article_url": url,
                    "content": f"{title} (часть {part_num})\n\n" + "\n".join(current),
                    "source_platform": "civil_code",
                    "metadata": json.dumps({
                        "article_num": num,
                        "lang": lang,
                        "part": part,
                        "source": source_label,
                    }, ensure_ascii=False),
                })

    return chunks


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    all_chunks = []

    for i, src in enumerate(SOURCES):
        print(f"\n[{i+1}/{len(SOURCES)}] {src['source']}")
        try:
            articles = fetch_articles(src)
            chunks = make_chunks(articles, src)
            all_chunks.extend(chunks)
            print(f"  -> Чанков: {len(chunks)}")
            if i < len(SOURCES) - 1:
                time.sleep(2)
        except Exception as e:
            print(f"  ОШИБКА: {e}")
            import traceback
            traceback.print_exc()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"\nИтого: {len(all_chunks)} чанков -> {OUTPUT_FILE}")
    print("Следующий шаг: python upload_platform.py --platform civil_code")


if __name__ == "__main__":
    main()
