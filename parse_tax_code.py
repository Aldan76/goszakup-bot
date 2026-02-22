"""
parse_tax_code.py — Парсер Налогового кодекса РК с adilet.zan.kz

Извлекает статьи о:
- НДС в госзакупках
- Счетах-фактурах
- Налоговых льготах
- Налоговых резидентах
- Учете доходов/расходов

Статьи парсятся по коду документа и сохраняются в chunks_tax.json
"""

import re
import json
import hashlib
from datetime import datetime
from urllib.parse import urljoin
import httpx

# ─── Конфиг ───────────────────────────────────────────────────────────────

BASE_URL = "https://adilet.zan.kz/rus/docs"

# Налоговый кодекс РК — различные версии могут быть
# K080000210_ — основной (по состоянию на февраль 2026)
# Нужно проверить актуальную версию

TAX_CODE_ID = "K080000210_"  # Укажи актуальный код после проверки на adilet

# Ключевые статьи для экстракции (по приоритету)
KEY_ARTICLES = {
    # НДС (высокий приоритет)
    "НДС": [
        ("148", "Основные положения об НДС"),
        ("149", "Плательщики НДС"),
        ("150", "Налоговые резиденты и нерезиденты"),
        ("151", "Объект налогообложения НДС"),
        ("153", "Налоговая база НДС"),
        ("154", "Налоговая ставка НДС"),
        ("155", "Входной НДС"),
        ("156", "Вычет НДС"),
        ("157", "Авансы и переплаты НДС"),
        ("158", "Зачет и возврат НДС"),
        ("163", "Счета-фактуры"),
    ],

    # Налоговые льготы
    "ЛЬГОТЫ": [
        ("231", "Объекты налогового льготирования"),
        ("232", "Налоговые льготы для СЭЗ"),
        ("233", "Льготы для МСБ"),
        ("234", "Льготы для субъектов соцпредпринимательства"),
        ("235", "Льготы для благотворительных организаций"),
        ("236", "Льготы для образования и здравоохранения"),
    ],

    # Учет и документы
    "УЧЕТ": [
        ("325", "Признание доходов"),
        ("330", "Признание расходов"),
        ("340", "Документирование доходов и расходов"),
        ("350", "Ведение налогового учета"),
    ],

    # Налоговый контроль
    "КОНТРОЛЬ": [
        ("407", "Налоговые проверки"),
        ("410", "Налоговые требования"),
        ("420", "Налоговые санкции и штрафы"),
        ("468", "Штрафные санкции"),
    ],
}

# ─── Парсер ───────────────────────────────────────────────────────────────

def fetch_article(article_num: str) -> dict | None:
    """
    Загружает статью из Налогового кодекса по номеру.
    Возвращает dict с текстом и метаданными или None если не найдена.
    """
    url = f"{BASE_URL}/{TAX_CODE_ID}/z{article_num:0>3}"

    try:
        print(f"  Загружаю статью {article_num}...", end=" ")

        response = httpx.get(url, timeout=10, follow_redirects=True)

        if response.status_code == 404:
            print("❌ не найдена")
            return None

        if response.status_code != 200:
            print(f"⚠️ ошибка {response.status_code}")
            return None

        # Простой парсинг HTML (извлекаем <h3> заголовки и <p> текст)
        html = response.text

        # Пытаемся извлечь заголовок статьи
        title_match = re.search(r'<h2[^>]*>Статья\s+(\d+)[^<]*</h2>\s*([^<]+)', html)
        if not title_match:
            title_match = re.search(r'<h3[^>]*>Статья\s+(\d+)[^<]*</h3>\s*([^<]+)', html)

        if title_match:
            title = title_match.group(2).strip()
        else:
            title = f"Статья {article_num}"

        # Извлекаем весь текст статьи (между заголовком и следующей статьей)
        # Это упрощенный вариант — в реальности нужна более сложная логика
        content_match = re.search(
            f'<h[23][^>]*>Статья\\s+{article_num}[^<]*</h[23]>(.+?)(?=<h[23]|$)',
            html,
            re.DOTALL | re.IGNORECASE
        )

        if content_match:
            # Очищаем HTML теги
            text = re.sub(r'<[^>]+>', '\n', content_match.group(1))
            text = re.sub(r'\n+', '\n', text).strip()
        else:
            print("⚠️ текст не найден")
            return None

        print(f"✅ загружена ({len(text)} символов)")

        return {
            "article_num": article_num,
            "title": title,
            "text": text,
            "url": url,
        }

    except Exception as e:
        print(f"❌ ошибка: {e}")
        return None


def create_chunks(articles: list[dict]) -> list[dict]:
    """
    Преобразует загруженные статьи в чанки для векторной БД.
    """
    chunks = []
    date_suffix = datetime.now().strftime("%Y%m%d")

    for idx, article in enumerate(articles, 1):
        # Уникальный ID чанка
        article_hash = hashlib.md5(article["title"].encode()).hexdigest()[:8]
        chunk_id = f"tax_{article['article_num']}_{article_hash}_{date_suffix}_{idx:03d}"

        # Разбиваем большие статьи на подчанки (если нужно)
        text = article["text"]
        parts = text.split("\n\n")

        for part_idx, part in enumerate(parts, 1):
            if len(part.strip()) < 20:
                continue

            chunk = {
                "id": f"{chunk_id}_{part_idx:02d}" if len(parts) > 1 else chunk_id,
                "document_short": "НК РК",
                "source_platform": "tax",  # ← важно для фильтрации в RAG
                "article_title": f"Статья {article['article_num']}. {article['title']}",
                "chapter": f"Налоговый кодекс РК",
                "text": part.strip(),
                "official_url": article["url"],
                "metadata": {
                    "type": "tax_code",
                    "article_num": article["article_num"],
                    "section": article.get("section", ""),
                }
            }
            chunks.append(chunk)

    return chunks


def main():
    """Основная функция: парсит статьи и сохраняет в JSON."""

    print("=" * 70)
    print("ПАРСЕР НАЛОГОВОГО КОДЕКСА РК")
    print("=" * 70)

    # Флаттим словарь KEY_ARTICLES в список (section, num, title)
    articles_to_fetch = []
    for section, article_list in KEY_ARTICLES.items():
        for article_num, article_title in article_list:
            articles_to_fetch.append({
                "section": section,
                "article_num": article_num,
                "article_title": article_title,
            })

    print(f"\nВсего статей к загрузке: {len(articles_to_fetch)}")
    print(f"Источник: {BASE_URL}/{TAX_CODE_ID}\n")

    # Загружаем статьи
    loaded_articles = []

    for item in articles_to_fetch:
        section = item["section"]
        article_num = item["article_num"]

        # Загружаем статью
        article = fetch_article(article_num)

        if article:
            article["section"] = section
            loaded_articles.append(article)

    print(f"\n✅ Успешно загружено: {len(loaded_articles)} статей из {len(articles_to_fetch)}")

    # Создаем чанки
    print("\n" + "=" * 70)
    print("СОЗДАНИЕ ЧАНКОВ")
    print("=" * 70)

    chunks = create_chunks(loaded_articles)

    print(f"✅ Создано чанков: {len(chunks)}")

    # Сохраняем в JSON
    output_file = "data/chunks_tax.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"✅ Сохранено в: {output_file}")

    # Статистика
    print("\n" + "=" * 70)
    print("СТАТИСТИКА")
    print("=" * 70)

    by_section = {}
    for chunk in chunks:
        section = chunk["metadata"].get("section", "неизвестно")
        by_section[section] = by_section.get(section, 0) + 1

    for section, count in sorted(by_section.items()):
        print(f"{section:12} — {count:3} чанков")

    print(f"\nИТОГО: {len(chunks)} чанков")
    print(f"\nФайл готов к загрузке в Supabase через upload_platform.py")
    print(f"Команда: python upload_platform.py --chunks data/chunks_tax.json --platform tax")


if __name__ == "__main__":
    main()
