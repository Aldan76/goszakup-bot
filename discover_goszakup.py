"""
discover_goszakup.py — Discover available pages on wiki.goszakup.gov.kz
"""

import httpx
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

class LinkExtractor(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.links = set()
        self.base_url = base_url

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href' and value:
                    # Make absolute URL
                    url = urljoin(self.base_url, value)
                    # Keep only wiki pages
                    if 'wiki.goszakup.gov.kz' in url and not url.endswith(('.css', '.js', '.jpg', '.png')):
                        # Remove fragments
                        if '#' in url:
                            url = url.split('#')[0]
                        self.links.add(url)

client = httpx.Client(timeout=10)
base_url = "https://wiki.goszakup.gov.kz/"

try:
    print("Fetching wiki.goszakup.gov.kz...")
    response = client.get(base_url, follow_redirects=True)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        extractor = LinkExtractor(base_url)
        extractor.feed(response.text)

        # Filter to get main article pages
        wiki_pages = [url for url in extractor.links
                     if 'index.php' in url and not 'Special:' in url
                     and not 'User:' in url and not 'Talk:' in url]

        print(f"\nFound {len(wiki_pages)} pages:\n")
        for url in sorted(wiki_pages)[:30]:
            # Extract page title from URL
            match = re.search(r'index\.php[/?](.+?)(?:&|$)', url)
            title = match.group(1) if match else url.split('/')[-1]
            print(f"  {title}")
            print(f"    {url}")

except Exception as e:
    print(f"Error: {e}")

client.close()
