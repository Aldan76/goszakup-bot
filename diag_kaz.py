import httpx, re, html as html_mod

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "kk-KZ,kk;q=0.9,ru;q=0.8",
    "Connection": "keep-alive",
}

url = "https://adilet.zan.kz/kaz/docs/K990000409_"
resp = httpx.get(url, headers=HEADERS, timeout=60, follow_redirects=True, verify=False)

print(f"Final URL: {resp.url}")
print(f"Status: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('content-type', 'N/A')}")

# Считаем H3 с id="z..."
TAG_RE = re.compile(r'<(h3|p)\s[^>]*id="(z\d+)"[^>]*>(.*?)<\/\1>', re.DOTALL | re.IGNORECASE)
TAG_STRIP = re.compile(r'<[^>]+>')

def clean(raw):
    t = TAG_STRIP.sub(' ', raw)
    t = html_mod.unescape(t)
    return re.sub(r'\s+', ' ', t).strip()

h3s = [(m.group(2), clean(m.group(3))) for m in TAG_RE.finditer(resp.text) if m.group(1).lower() == 'h3']
print(f"Всего H3 с id=z*: {len(h3s)}")
print("Первые 10 H3:")
for el_id, text in h3s[:10]:
    print(f"  {el_id}: {repr(text[:80])}")

# Проверяем regex
art_re = re.compile(r'(\d+)-б[аа]п')
matched = [(el_id, t) for el_id, t in h3s if art_re.search(t)]
print(f"\nH3 совпадающих с regex '(\d+)-б[аа]п': {len(matched)}")
for el_id, t in matched[:5]:
    print(f"  {el_id}: {repr(t[:60])}")
