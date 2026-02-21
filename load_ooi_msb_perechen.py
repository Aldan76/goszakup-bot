"""
load_ooi_msb_perechen.py — Парсер и загрузчик перечней ТРУ:
  1. Приказ Минтруда №345 (ООИ) — V2400035032
     Перечень отдельных видов ТРУ, закупаемых у организаций лиц с инвалидностью
  2. Приказ МФ №677 (МСБ) — V2400035226
     Перечень ТРУ, закупаемых у субъектов малого и среднего предпринимательства

ПЕРЕД ЗАПУСКОМ: выполните supabase_ktru_alter.sql в Supabase SQL Editor.

Запуск:
    python load_ooi_msb_perechen.py
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

# ─── Вспомогательные функции ───────────────────────────────────────────────

def strip_tags(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_html_paragraphs(html_path: str) -> list[str]:
    with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>',  ' ', html, flags=re.DOTALL | re.IGNORECASE)
    parts = re.split(r'<(?:p|div|h[1-6]|li|tr|td|th|br)\b[^>]*>', html, flags=re.IGNORECASE)
    return [strip_tags(p) for p in parts if len(strip_tags(p)) > 5]


# ─── Паттерн ЕКТРУ-кода ────────────────────────────────────────────────────
# Примеры: 139212.700.000001, 310312.7/9, 013010.210.000000
RE_EKTRU = re.compile(r'^\d{6}[\d./x]+', re.IGNORECASE)


# ─── 1. Парсер ООИ (Приказ №345) ──────────────────────────────────────────

def parse_ooi(html_path: str) -> list[dict]:
    """
    Парсит Перечень ООИ (Приказ Минтруда №345).
    Структура таблицы: наименование / код ЕКТРУ (один или несколько строк кодов).
    Объединяет строки кодов к соответствующему наименованию.
    Разделы: «Раздел 1. Производимые товары», «Раздел 2. Выполняемые работы»,
             «Раздел 3. Оказываемые услуги».
    """
    paragraphs = parse_html_paragraphs(html_path)

    NPA_NAME = "Приказ Минтруда и соцзащиты РК от 03.09.2024 №345 (рег. №35032)"
    NPA_URL  = "https://adilet.zan.kz/rus/docs/V2400035032"
    SPOSOB   = "Закупка у организаций лиц с инвалидностью (ООИ) — конкурс или запрос ценовых предложений"

    # Определяем начало таблицы по заголовку «Наименование»
    start = None
    for i, p in enumerate(paragraphs):
        if re.match(r'^наименование\b', p, re.IGNORECASE) and i < 120:
            start = i + 1
            break

    if start is None:
        print("  ОШИБКА: не найден заголовок таблицы ООИ")
        return []

    items = []
    current_razdel = "Товары"
    current_name = None
    current_codes = []
    num = 0

    RAZD_MAP = {
        "1": "Товары",
        "2": "Работы",
        "3": "Услуги",
    }

    for p in paragraphs[start:]:
        # Конец таблицы — footer сайта или сообщение об ошибке
        if re.search(
            r'обнаружили.*ошибку|состояние базы|всего документов|'
            r'правовая информационная|пользовательское соглашение|'
            r'обратная связь|карта сайта|служба поддержки|популярные документы|'
            r'последние документы|трудовой кодекс|налоговый кодекс',
            p, re.IGNORECASE
        ):
            break

        # Определяем раздел по заголовку «1. Производимые товары:» или «Раздел 1»
        m_razd = re.match(r'(?:Раздел\s+)?(\d+)[.\)]\s+(Производимые|Выполняемые|Оказываемые)', p, re.IGNORECASE)
        if m_razd:
            # Сохраняем предыдущую позицию
            if current_name and not RE_EKTRU.match(current_name):
                codes_str = "; ".join(current_codes) if current_codes else None
                num += 1
                items.append({
                    "num": num,
                    "nazvanie": current_name,
                    "sposob": SPOSOB,
                    "osnovaniye": NPA_NAME,
                    "npa_url": NPA_URL,
                    "perechen_type": "ooi",
                    "razdel": current_razdel,
                    "ektru_codes": codes_str,
                })
                current_name = None
                current_codes = []
            kw = m_razd.group(2).lower()
            if 'производим' in kw:
                current_razdel = "Товары"
            elif 'выполняем' in kw:
                current_razdel = "Работы"
            elif 'оказываем' in kw:
                current_razdel = "Услуги"
            else:
                current_razdel = RAZD_MAP.get(m_razd.group(1), p[:30])
            continue

        # Пропускаем заголовки колонок и технические строки
        if re.match(r'^(наименование|код\s+по|ектру|енсктру)', p, re.IGNORECASE):
            continue
        if re.match(r'^(приложение|утвержд|приказ|редакц)', p, re.IGNORECASE):
            continue
        # Пропускаем заголовки разделов (они уже обработаны выше)
        if re.match(r'^\d+[.\)]\s+(?:Производимые|Выполняемые|Оказываемые)', p, re.IGNORECASE):
            continue

        # Это код ЕКТРУ?
        if RE_EKTRU.match(p):
            if current_name:
                current_codes.append(p[:50])
            continue

        # Иначе это новое наименование ТРУ
        # Сохраняем предыдущую позицию
        if current_name and not RE_EKTRU.match(current_name):
            codes_str = "; ".join(current_codes) if current_codes else None
            num += 1
            items.append({
                "num": num,
                "nazvanie": current_name,
                "sposob": SPOSOB,
                "osnovaniye": NPA_NAME,
                "npa_url": NPA_URL,
                "perechen_type": "ooi",
                "razdel": current_razdel,
                "ektru_codes": codes_str,
            })

        current_name = p
        current_codes = []

    # Последняя позиция
    if current_name and not RE_EKTRU.match(current_name):
        codes_str = "; ".join(current_codes) if current_codes else None
        num += 1
        items.append({
            "num": num,
            "nazvanie": current_name,
            "sposob": SPOSOB,
            "osnovaniye": NPA_NAME,
            "npa_url": NPA_URL,
            "perechen_type": "ooi",
            "razdel": current_razdel,
            "ektru_codes": codes_str,
        })

    return items


# ─── 2. Данные МСБ (Приказ №677) ──────────────────────────────────────────

def get_msb_items() -> list[dict]:
    """
    Для МСБ (Приказ №677) конкретный перечень товаров не доступен в HTML
    (загружается динамически). Добавляем сводную запись о трёх категориях
    с правилами и порогом 50 000 МРП.
    """
    NPA_NAME = "Приказ МФ РК от 08.10.2024 №677 (рег. №35226)"
    NPA_URL  = "https://adilet.zan.kz/rus/docs/V2400035226"

    items = []
    for i, (razdel, nazvanie) in enumerate([
        ("Товары",  "Товары, закупаемые у субъектов малого и среднего предпринимательства (МСБ/МСП)"),
        ("Работы",  "Работы (не строительные), закупаемые у субъектов малого и среднего предпринимательства (МСБ/МСП)"),
        ("Услуги",  "Услуги, закупаемые у субъектов малого и среднего предпринимательства (МСБ/МСП)"),
    ], start=1):
        items.append({
            "num":          i,
            "nazvanie":     nazvanie,
            "sposob":       (
                "Закупка у субъектов МСБ/МСП — конкурс или запрос ценовых предложений. "
                "Условия: стоимость не превышает 50 000 МРП; поставщик является субъектом МСБ. "
                "При несостоявшейся закупке — закупка среди всех поставщиков."
            ),
            "osnovaniye":   NPA_NAME,
            "npa_url":      NPA_URL,
            "perechen_type": "msb",
            "razdel":       razdel,
            "ektru_codes":  None,
        })
    return items


# ─── 3. Загрузка в Supabase ────────────────────────────────────────────────

def upload_items(items: list[dict], label: str, perechen_type: str) -> bool:
    """Загружает позиции перечня в ktru_perechen (upsert по num+perechen_type)."""
    print(f"\nЗагружаем {len(items)} позиций [{label}] в Supabase...")

    # Удаляем старые записи этого типа
    del_req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/ktru_perechen?perechen_type=eq.{perechen_type}",
        method='DELETE',
        headers={
            'apikey':        SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer':        'return=minimal',
        }
    )
    try:
        with urllib.request.urlopen(del_req) as resp:
            print(f"  Очистка [{perechen_type}]: HTTP {resp.status}")
    except Exception as e:
        print(f"  Очистка [{perechen_type}]: {e}")

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
                razdel = item.get('razdel', '')
                print(f"  [{item['num']:3d}] OK [{razdel}]: {item['nazvanie'][:55]}")
        except urllib.error.HTTPError as e:
            errors += 1
            print(f"  [{item['num']:3d}] ERROR {e.code}: {e.read().decode()[:100]}")
        except Exception as e:
            errors += 1
            print(f"  [{item['num']:3d}] ERROR: {e}")
        time.sleep(0.05)

    print(f"  Итого: загружено {success}, ошибок {errors}")
    return errors == 0


# ─── main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("Загрузка Перечней ООИ (Приказ №345) и МСБ (Приказ №677)")
    print("=" * 65)

    all_items = []

    # ── ООИ ─────────────────────────────────────────────────────────────
    ooi_html = os.path.join(DATA_DIR, "raw_OOI_345.html")
    if not os.path.exists(ooi_html):
        print(f"\nФайл не найден: {ooi_html}")
        print("Скачайте: https://adilet.zan.kz/rus/docs/V2400035032")
    else:
        print(f"\n--- Парсим ООИ №345 ---")
        ooi_items = parse_ooi(ooi_html)
        print(f"Извлечено позиций ООИ: {len(ooi_items)}")

        # Сводка по разделам
        from collections import Counter
        razd_cnt = Counter(it['razdel'] for it in ooi_items)
        for r, c in razd_cnt.most_common():
            print(f"  {r}: {c} позиций")

        # Сохраняем JSON
        out_ooi = os.path.join(DATA_DIR, "ktru_ooi_345.json")
        with open(out_ooi, 'w', encoding='utf-8') as f:
            json.dump(ooi_items, f, ensure_ascii=False, indent=2)
        print(f"JSON: {out_ooi}")

        upload_items(ooi_items, "ООИ №345", "ooi")
        all_items.extend(ooi_items)

    # ── МСБ ─────────────────────────────────────────────────────────────
    print(f"\n--- Загружаем МСБ №677 ---")
    msb_items = get_msb_items()
    print(f"Позиций МСБ: {len(msb_items)}")
    for it in msb_items:
        print(f"  [{it['num']}] {it['nazvanie'][:60]}")

    out_msb = os.path.join(DATA_DIR, "ktru_msb_677.json")
    with open(out_msb, 'w', encoding='utf-8') as f:
        json.dump(msb_items, f, ensure_ascii=False, indent=2)
    print(f"JSON: {out_msb}")

    upload_items(msb_items, "МСБ №677", "msb")
    all_items.extend(msb_items)

    print(f"\n{'='*65}")
    print(f"ИТОГО загружено позиций: {len(all_items)}")
    print(f"  ООИ: {sum(1 for it in all_items if it['perechen_type']=='ooi')}")
    print(f"  МСБ: {sum(1 for it in all_items if it['perechen_type']=='msb')}")
    print("Готово!")


if __name__ == '__main__':
    main()
