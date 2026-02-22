"""Детальный осмотр параграфов 85-200."""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\fazyl\Documents\Project1\goszakup-bot\data\raw_Metodika_DVC_260.html',
          'r', encoding='utf-8', errors='replace') as f:
    html = f.read()

import html as html_module
html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
parts = re.split(r'<(?:p|div|h[1-6]|li|tr|td|br)\b[^>]*>', html, flags=re.IGNORECASE)

def strip_tags(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

paragraphs = [strip_tags(p) for p in parts if len(strip_tags(p)) > 5]

print("--- Параграфы 85-200 ---")
for i, p in enumerate(paragraphs[85:200], start=85):
    print(f"  [{i:3d}] {p[:120]}")
