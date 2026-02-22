"""Разведка структуры HTML Методики ДВЦ — ищем начало документа."""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\fazyl\Documents\Project1\goszakup-bot\data\raw_Metodika_DVC_260.html',
          'r', encoding='utf-8', errors='replace') as f:
    html = f.read()

import html as html_module

# Удаляем скрипты/стили
html_clean = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
html_clean = re.sub(r'<style[^>]*>.*?</style>', ' ', html_clean, flags=re.DOTALL|re.IGNORECASE)

parts = re.split(r'<(?:p|div|h[1-6]|li|tr|td|br)\b[^>]*>', html_clean, flags=re.IGNORECASE)

def strip_tags(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

paragraphs = [strip_tags(p) for p in parts if len(strip_tags(p)) > 5]

# Ищем параграфы содержащие ключевые слова документа
print("--- Параграфы с 'Методика' или 'ДВЦ' или 'внутристрановой' ---")
for i, p in enumerate(paragraphs):
    if any(kw in p.lower() for kw in ['методика', 'двц', 'внутристрановой', 'статья', 'пункт']):
        print(f"  [{i:3d}] {p[:120]}")

print("\n--- Параграфы 30-80 (вся структура) ---")
for i, p in enumerate(paragraphs[30:80], start=30):
    print(f"  [{i:3d}] {p[:110]}")
