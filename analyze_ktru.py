"""
analyze_ktru.py — Анализ чата на упоминания КТРУ, перечней товаров,
способов закупки связанных с правительственными перечнями.
"""
import sys
import json
import re
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

CHAT_PATH = r"C:\Users\fazyl\Downloads\проект Госзакуп\result.json"

with open(CHAT_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

messages = data.get('messages', [])

def get_text(msg):
    t = msg.get('text', '')
    if isinstance(t, list):
        return ' '.join(p if isinstance(p, str) else p.get('text','') for p in t)
    return str(t)

# Ключевые слова по теме
KTRU_PATTERNS = [
    r'КТРУ', r'ктру', r'классификатор\s+товаров', r'КТРУ',
    r'перечень\s+товаров', r'перечень\s+работ', r'перечень\s+услуг',
    r'постановление\s+правительства',
    r'ПП\s*№?\s*\d+',  # ПП №XXX
    r'способ\s+закупки.*перечн',
    r'единый\s+источник.*перечн',
    r'из\s+одного\s+источника.*перечн',
    r'перечн.*из\s+одного\s+источника',
    r'товар.*код', r'код.*товар',
    r'неконкурентн',
    r'закупка.*перечн',
    r'обязательн.*перечн',
    r'приказ.*перечн',
    r'товаров\s+отечественного',
    r'казахстанского\s+содержания.*перечн',
    r'\bКТП.*перечн\b',
    r'номенклатур',
]

print("=" * 70)
print("Анализ чата: упоминания КТРУ и перечней товаров")
print("=" * 70)

relevant_msgs = []
for msg in messages:
    text = get_text(msg)
    if len(text) < 10:
        continue
    for pat in KTRU_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            relevant_msgs.append({
                'date': msg.get('date', '')[:10],
                'from': msg.get('from', 'unknown')[:20],
                'text': text,
                'pattern': pat
            })
            break

print(f"\nНайдено сообщений с упоминанием перечней/КТРУ: {len(relevant_msgs)}")

# Группируем по паттернам
pattern_counts = Counter(m['pattern'] for m in relevant_msgs)
print("\n--- По паттернам ---")
for pat, cnt in pattern_counts.most_common():
    print(f"  {cnt:3d}  {pat}")

# Выводим уникальные сообщения
print("\n--- Примеры сообщений (первые 30) ---")
seen = set()
shown = 0
for m in relevant_msgs:
    key = m['text'][:80]
    if key in seen:
        continue
    seen.add(key)
    print(f"\n  [{m['date']}] {m['from']}:")
    print(f"  {m['text'][:300]}")
    shown += 1
    if shown >= 30:
        break

# Ищем конкретные номера постановлений/приказов с перечнями
print("\n\n--- Упоминания конкретных НПА с перечнями ---")
npa_pattern = re.compile(
    r'(?:постановление|приказ|пп|пост\.?)\s*(?:правительства\s*рк\s*)?'
    r'(?:от\s*[\d.]+\s*(?:года|г\.?)?\s*)?'
    r'№?\s*(\d{1,4})',
    re.IGNORECASE
)
npa_counter = Counter()
for msg in messages:
    text = get_text(msg)
    if any(re.search(p, text, re.IGNORECASE) for p in [r'перечн', r'КТРУ', r'ктру', r'номенклатур']):
        for m in npa_pattern.finditer(text):
            npa_counter[m.group(0)[:50].strip()] += 1

print("Топ упоминаемых НПА в контексте перечней:")
for npa, cnt in npa_counter.most_common(20):
    print(f"  {cnt:3d}  {npa}")
