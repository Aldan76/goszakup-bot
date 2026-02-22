"""Разведка структуры HTML Методики ДВЦ."""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\fazyl\Documents\Project1\goszakup-bot\data\raw_Metodika_DVC_260.html',
          'r', encoding='utf-8', errors='replace') as f:
    html = f.read()

print(f"Размер: {len(html):,} символов")

# Удаляем скрипты/стили
html_clean = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
html_clean = re.sub(r'<style[^>]*>.*?</style>', ' ', html_clean, flags=re.DOTALL|re.IGNORECASE)

# Разбиваем на параграфы
import html as html_module
parts = re.split(r'<(?:p|div|h[1-6]|li|tr|td|br)\b[^>]*>', html_clean, flags=re.IGNORECASE)

def strip_tags(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

paragraphs = [strip_tags(p) for p in parts if len(strip_tags(p)) > 5]
print(f"Параграфов: {len(paragraphs)}")

# Ищем структурные элементы
RE_CHAPTER  = re.compile(r'^Глава\s+(\d+)[.\s]*(.*)', re.IGNORECASE)
RE_SECTION  = re.compile(r'^(?:Раздел|РАЗДЕЛ)\s+(\d+[\w.-]*)[.\s]*(.*)')
RE_PUNKT    = re.compile(r'^(\d{1,3})\.\s+\S')
RE_APPENDIX = re.compile(r'^Приложение\s+(\d+[\w-]*)[.\s]*(.*)', re.IGNORECASE)
RE_FORMULA  = re.compile(r'формул[аы]|ДВЦ\s*=|КТП\s*=', re.IGNORECASE)

print("\n--- Структура документа ---")
for p in paragraphs:
    if RE_CHAPTER.match(p):
        print(f"  ГЛАВА:    {p[:90]}")
    elif RE_SECTION.match(p):
        print(f"  РАЗДЕЛ:   {p[:90]}")
    elif RE_APPENDIX.match(p):
        print(f"  ПРИЛ:     {p[:90]}")

print("\n--- Первые 30 параграфов ---")
for i, p in enumerate(paragraphs[:30]):
    print(f"  [{i:2d}] {p[:100]}")

print("\n--- Параграфы с формулами ---")
for i, p in enumerate(paragraphs):
    if RE_FORMULA.search(p):
        print(f"  [{i}] {p[:120]}")
