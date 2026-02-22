"""
scrape_goszakup.py — Scrape instructions from wiki.goszakup.gov.kz pages

Usage:
    python scrape_goszakup.py

Saves to data/raw_goszakup_wiki.txt in format:
    === PAGE: title ===
    Content...
    === END ===
"""

import httpx
import re
from pathlib import Path
from html import unescape

# Основные инструкции на goszakup wiki (примерный список)
PAGES_TO_SCRAPE = [
    # Основные инструкции
    ("Как начать работу", "https://wiki.goszakup.gov.kz/index.php/"),
    ("Регистрация", "https://wiki.goszakup.gov.kz/index.php/Регистрация"),
    ("Авторизация", "https://wiki.goszakup.gov.kz/index.php/Авторизация"),
    ("Личный кабинет", "https://wiki.goszakup.gov.kz/index.php/Личный_кабинет"),
    ("Профиль пользователя", "https://wiki.goszakup.gov.kz/index.php/Профиль_пользователя"),

    # Заказчики
    ("Создание закупки", "https://wiki.goszakup.gov.kz/index.php/Создание_закупки"),
    ("Способы закупок", "https://wiki.goszakup.gov.kz/index.php/Способы_закупок"),
    ("Конкурс", "https://wiki.goszakup.gov.kz/index.php/Конкурс"),
    ("Запрос ценового предложения", "https://wiki.goszakup.gov.kz/index.php/Запрос_ценового_предложения"),
    ("Запрос котировок", "https://wiki.goszakup.gov.kz/index.php/Запрос_котировок"),
    ("Единый источник", "https://wiki.goszakup.gov.kz/index.php/Единый_источник"),
    ("Прямые закупки", "https://wiki.goszakup.gov.kz/index.php/Прямые_закупки"),
    ("Электронный аукцион", "https://wiki.goszakup.gov.kz/index.php/Электронный_аукцион"),

    # Поставщики
    ("Участие в закупках", "https://wiki.goszakup.gov.kz/index.php/Участие_в_закупках"),
    ("Подача предложения", "https://wiki.goszakup.gov.kz/index.php/Подача_предложения"),
    ("Договор", "https://wiki.goszakup.gov.kz/index.php/Договор"),

    # Дополнительно
    ("Жалобы", "https://wiki.goszakup.gov.kz/index.php/Жалобы"),
    ("FAQ", "https://wiki.goszakup.gov.kz/index.php/FAQ"),
]


def extract_text(html_content):
    """Извлекает текст из HTML, удаляет скрипты и стили."""
    # Удаляем скрипты и стили
    html = re.sub(r'<script.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Удаляем навигацию и боковые панели
    html = re.sub(r'<nav.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<aside.*?</aside>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'class="[^"]*sidebar[^"]*"[^>]*>.*?</[^>]*>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Заменяем теги на переносы строк
    html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</div>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</li>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)

    # Декодируем HTML сущности
    text = unescape(html)

    # Очищаем от лишних пробелов
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)


def scrape_pages():
    """Скрапит все страницы и сохраняет в файл."""
    client = httpx.Client(timeout=15)
    output = Path("data/raw_goszakup_wiki.txt")

    print(f"Scraping goszakup wiki to {output}")
    print("=" * 70)

    with open(output, 'w', encoding='utf-8') as f:
        total = len(PAGES_TO_SCRAPE)

        for i, (page_title, url) in enumerate(PAGES_TO_SCRAPE, 1):
            try:
                print(f"[{i:2d}/{total}] {page_title:30s} ... ", end='', flush=True)

                response = client.get(url, follow_redirects=True)
                response.raise_for_status()

                text = extract_text(response.text)

                if len(text) > 50:  # Only save if content is significant
                    f.write(f"=== PAGE: {page_title} ===\n")
                    f.write(text)
                    f.write("\n=== END ===\n\n")
                    print(f"OK ({len(text)} chars)")
                else:
                    print("Empty or 404")

            except Exception as e:
                print(f"Error: {str(e)[:40]}")

    print("=" * 70)
    print(f"Saved to: {output}")
    print(f"File size: {output.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    scrape_pages()
