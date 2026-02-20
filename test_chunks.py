"""
test_chunks.py — Локальный тест поиска по чанкам БЕЗ API.

Запуск:
    python test_chunks.py

Что делает:
- Ищет по ключевым словам в тексте чанков
- Показывает релевантные куски текста
- Проверяет что парсинг прошёл правильно
- Ничего не стоит — никакого API
"""

import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "data", "chunks_all.json")

with open(CHUNKS_PATH, encoding="utf-8") as f:
    CHUNKS = json.load(f)


# ─── Поиск ────────────────────────────────────────────────────────────────────

def search(query: str, top_n: int = 3) -> list[dict]:
    """
    Простой keyword-поиск по чанкам.
    Возвращает top_n наиболее релевантных чанков.
    """
    keywords = query.lower().split()
    scored = []

    for chunk in CHUNKS:
        text_lower = chunk["text"].lower()
        title_lower = (chunk.get("article_title") or chunk.get("chapter", "")).lower()

        score = 0
        for kw in keywords:
            # Совпадение в тексте
            count = text_lower.count(kw)
            score += count

            # Совпадение в заголовке — весомее
            if kw in title_lower:
                score += 10

        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:top_n]]


def highlight(text: str, query: str, context_chars: int = 300) -> str:
    """
    Находит первое вхождение ключевого слова и показывает контекст вокруг него.
    """
    keywords = query.lower().split()
    text_lower = text.lower()

    best_pos = len(text)
    for kw in keywords:
        pos = text_lower.find(kw)
        if pos != -1 and pos < best_pos:
            best_pos = pos

    if best_pos == len(text):
        return text[:context_chars * 2] + "..."

    start = max(0, best_pos - context_chars // 2)
    end   = min(len(text), best_pos + context_chars)
    snippet = text[start:end]

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


def show_result(chunk: dict, query: str):
    """Красиво выводит один результат поиска."""
    title = chunk.get("article_title") or chunk.get("chapter", "")
    doc   = chunk["document_short"]
    url   = chunk["official_url"]
    cid   = chunk["id"]

    print(f"\n  [{cid}] {doc}")
    print(f"  {title}")
    print(f"  Ссылка: {url}")
    print(f"  Фрагмент:")
    snippet = highlight(chunk["text"], query)
    # Отступ для читаемости
    for line in snippet.split('\n'):
        if line.strip():
            print(f"    {line.strip()}")
    print()


# ─── Интерактивный режим ──────────────────────────────────────────────────────

def interactive():
    print("=" * 60)
    print("Поиск по базе госзакупок РК (без API, бесплатно)")
    print(f"Загружено чанков: {len(CHUNKS)}")
    print("Введите 'стат' — статистика базы")
    print("Введите 'выход' — выход")
    print("=" * 60)

    while True:
        try:
            query = input("\nПоиск: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break

        if not query:
            continue

        if query.lower() in ("выход", "exit", "quit"):
            print("До свидания!")
            break

        if query.lower() in ("стат", "stat", "статистика"):
            show_stats()
            continue

        results = search(query, top_n=3)

        if not results:
            print(f"\n  Ничего не найдено по запросу: '{query}'")
            print("  Попробуйте другие ключевые слова.")
            continue

        print(f"\nНайдено совпадений: {len(results)} (показаны лучшие)\n")
        print("-" * 60)
        for chunk in results:
            show_result(chunk, query)
            print("-" * 60)


def show_stats():
    """Выводит статистику базы знаний."""
    zakon   = [c for c in CHUNKS if c["source_type"] == "law"]
    pravila = [c for c in CHUNKS if c["source_type"] == "rules"]

    total_chars = sum(c["char_count"] for c in CHUNKS)
    est_tokens  = int(total_chars / 3.5)

    print(f"\n{'=' * 60}")
    print(f"СТАТИСТИКА БАЗЫ ЗНАНИЙ")
    print(f"{'=' * 60}")
    print(f"  Чанков Закона:   {len(zakon)}")
    print(f"  Чанков Правил:   {len(pravila)}")
    print(f"  Всего чанков:    {len(CHUNKS)}")
    print(f"  Всего символов:  {total_chars:,}")
    print(f"  ~Токенов:        {est_tokens:,} / 200,000")
    print()
    print("  Чанки Закона:")
    for c in zakon:
        title = (c.get("article_title") or "")[:55]
        print(f"    [{c['id']:15s}] {title}  ({c['char_count']} симв.)")
    print()
    print("  Чанки Правил:")
    for c in pravila:
        title = (c.get("article_title") or c.get("chapter", ""))[:55]
        print(f"    [{c['id']:20s}] {title}  ({c['char_count']} симв.)")
    print(f"{'=' * 60}")


# ─── Автотест с тестовыми вопросами ──────────────────────────────────────────

def run_autotest():
    """
    Прогоняет тестовые вопросы из ТЗ и показывает какие чанки находятся.
    Помогает убедиться что парсинг правильный.
    """
    test_questions = [
        "основания закупка из одного источника",
        "демпинговая цена меры",
        "неустойка просрочка расчет",
        "реестр недобросовестных поставщиков",
        "жалоба срок подачи",
        "электронный магазин закупки",
        "квалификационные требования поставщик",
        "изменения договор основания",
        "единый организатор централизованные закупки",
        "пролонгация договор питание",
    ]

    print("\n" + "=" * 60)
    print("АВТОТЕСТ — 10 тестовых вопросов из ТЗ")
    print("=" * 60)

    for i, q in enumerate(test_questions, 1):
        results = search(q, top_n=2)
        print(f"\n{i:2d}. Вопрос: '{q}'")
        if results:
            for r in results:
                title = r.get("article_title") or r.get("chapter", "")
                print(f"    -> [{r['id']}] {title[:65]}")
        else:
            print("    -> НЕ НАЙДЕНО")

    print(f"\n{'=' * 60}")
    print("Автотест завершён.")
    print("Если все вопросы находят релевантные чанки — парсинг OK.")
    print("=" * 60)


# ─── Точка входа ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "autotest":
        run_autotest()
    else:
        # Сначала показываем автотест, потом интерактив
        run_autotest()
        print("\nТеперь можете искать вручную:")
        interactive()
