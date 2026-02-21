"""
load_ktru_perechen.py — Парсер Приказа МФ РК №546 (Перечень ТРУ с предустановленным
способом закупки) и загрузчик в таблицу ktru_perechen Supabase.

Документ: https://adilet.zan.kz/rus/docs/V2400034933
Приказ МФ РК от 15.08.2024 №546 «Об утверждении Перечня товаров, работ, услуг,
по которым способ осуществления государственных закупок определяется
уполномоченным органом».

Запуск:
    python load_ktru_perechen.py
"""

import sys
import json
import re
import html as html_module
import os
import time
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
HTML_PATH = os.path.join(DATA_DIR, "raw_KTRU_546.html")

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

NPA_NAME = "Приказ МФ РК от 15.08.2024 №546, рег. №34933"
NPA_URL  = "https://adilet.zan.kz/rus/docs/V2400034933"


def strip_tags(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_perechen(html_path: str) -> list[dict]:
    """
    Парсит HTML Приказа №546 и извлекает позиции Перечня ТРУ.
    Структура Приложения 1:
      - строка-заголовок колонки: «Наименование товаров, работ, услуг»
      - строка-заголовок колонки: «Способ осуществления государственных закупок»
      - далее чередуются: наименование / способ
    Возвращает список dict с ключами num, nazvanie, sposob, osnovaniye, npa_url.
    """
    with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    # Убираем скрипты и стили
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>',  ' ', html, flags=re.DOTALL | re.IGNORECASE)

    # Разбиваем по блочным тегам
    parts = re.split(r'<(?:p|div|h[1-6]|li|tr|td|th|br)\b[^>]*>', html, flags=re.IGNORECASE)
    paragraphs = [strip_tags(p) for p in parts if len(strip_tags(p)) > 5]

    # Находим начало Приложения 1 (содержит перечень) — ищем заголовок таблицы
    start_idx = None
    for i, p in enumerate(paragraphs):
        if re.search(r'наименование\s+товаров.*работ.*услуг', p, re.IGNORECASE):
            start_idx = i
            break

    if start_idx is None:
        print("ОШИБКА: Не найден заголовок таблицы Перечня!")
        return []

    # После заголовка двух колонок идут пары: наименование / способ
    # Пропускаем два заголовка колонок (наименование и способ)
    data_start = start_idx + 2

    items = []
    num = 1
    i = data_start
    while i < len(paragraphs):
        p = paragraphs[i]

        # Конец Приложения 1 — начало Приложения 2 или сноски
        if re.match(r'приложение\s+2\b', p, re.IGNORECASE):
            break
        if re.match(r'сноска\b', p, re.IGNORECASE):
            break
        # Конец — навигационный footer
        if len(p) < 8:
            i += 1
            continue

        nazvanie = p
        # Следующая строка — способ закупки
        sposob_raw = paragraphs[i + 1] if i + 1 < len(paragraphs) else ""

        # Проверяем что это действительно способ закупки (содержит «конкурс», «аукцион» и т.д.)
        if re.search(r'конкурс|аукцион|запрос\s+ценовых|из\s+одного\s+источника|единственн', sposob_raw, re.IGNORECASE):
            items.append({
                "num":        num,
                "nazvanie":   nazvanie,
                "sposob":     sposob_raw,
                "osnovaniye": NPA_NAME,
                "npa_url":    NPA_URL,
            })
            num += 1
            i += 2  # пропускаем пару
        else:
            # Если следующая строка не похожа на способ — пропускаем
            i += 1

    return items


def upload_to_supabase(items: list[dict]) -> bool:
    """Загружает позиции перечня в таблицу ktru_perechen через upsert."""
    print(f"\nЗагружаем {len(items)} позиций в Supabase (ktru_perechen)...")

    # Сначала очищаем таблицу (перезапись с нуля при каждом запуске)
    del_req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/ktru_perechen?id=gte.0",
        method='DELETE',
        headers={
            'apikey':        SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer':        'return=minimal',
        }
    )
    try:
        with urllib.request.urlopen(del_req) as resp:
            print(f"  Очистка таблицы: HTTP {resp.status}")
    except Exception as e:
        print(f"  Очистка: {e} (таблица возможно пуста)")

    success, errors = 0, 0
    for item in items:
        body = json.dumps(item, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/ktru_perechen",
            data=body, method='POST',
            headers={
                'Content-Type': 'application/json',
                'apikey':        SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Prefer':        'resolution=merge-duplicates',
            }
        )
        try:
            with urllib.request.urlopen(req) as resp:
                success += 1
                print(f"  [{item['num']:2d}] OK: {item['nazvanie'][:60]}")
        except urllib.error.HTTPError as e:
            errors += 1
            print(f"  [{item['num']:2d}] ERROR {e.code}: {e.read().decode()[:100]}")
        except Exception as e:
            errors += 1
            print(f"  [{item['num']:2d}] ERROR: {e}")
        time.sleep(0.1)

    print(f"\nЗагружено: {success}, Ошибок: {errors}")
    return errors == 0


def main():
    print("=" * 65)
    print("Загрузка Перечня ТРУ (Приказ МФ РК №546, рег. №34933)")
    print("=" * 65)

    if not os.path.exists(HTML_PATH):
        print(f"ОШИБКА: файл не найден: {HTML_PATH}")
        print("Скачайте HTML с https://adilet.zan.kz/rus/docs/V2400034933")
        return

    items = parse_perechen(HTML_PATH)

    print(f"\nИзвлечено позиций: {len(items)}")
    for item in items:
        print(f"  [{item['num']:2d}] {item['nazvanie'][:60]}")
        print(f"       Способ: {item['sposob']}")

    if not items:
        print("Нечего загружать!")
        return

    # Сохраняем JSON
    out_path = os.path.join(DATA_DIR, "ktru_perechen.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"\nJSON сохранён: {out_path}")

    ok = upload_to_supabase(items)
    if ok:
        print("\n✅ Все позиции загружены в Supabase (ktru_perechen)!")
    else:
        print("\n⚠️  Есть ошибки при загрузке.")


if __name__ == '__main__':
    main()
