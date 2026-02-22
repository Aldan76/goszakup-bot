"""
scrape_goszakup_fixed.py — Scrape instructions from goszakup.gov.kz wiki

Found page IDs through exploration of Confluence wiki structure.
Uses pageId URLs which work correctly in Confluence.

Usage:
    python scrape_goszakup_fixed.py
"""

import httpx
import re
from pathlib import Path
from html import unescape

# Page IDs discovered on wiki.goszakup.gov.kz
PAGE_IDS = [
    (1310911, "Registering and Login"),
    (1310928, "Procurement Methods Guide"),
    (1310930, "Using Electronic Catalog"),
    (1310932, "Creating Procurement"),
    (1310934, "Electronic Auction Rules"),
    (1310943, "Guidelines for Participants"),
    (1310959, "Special Procurement Rules"),
]


def extract_page_content(html):
    """Extract main content from Confluence HTML page."""
    # Remove scripts and styles
    html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL)
    html = re.sub(r'<noscript.*?</noscript>', '', html, flags=re.DOTALL)

    # Extract title from <title> tag
    title_match = re.search(r'<title>([^<]+?)</title>', html)
    if title_match:
        title = title_match.group(1).strip()
        # Remove wiki suffix if present
        title = re.sub(r'\s*-\s*\w+\s*-\s*.*?$', '', title)
    else:
        title = "Unknown"

    # Try multiple selectors for Confluence content
    content = None

    # Try: div id="main-content" or id="content"
    for selector in ['main-content', 'content']:
        content_match = re.search(
            rf'<div\s+id="{selector}"[^>]*>(.*?)</div\s*>',
            html,
            re.DOTALL
        )
        if content_match:
            content = content_match.group(1)
            break

    # Try: div with class containing wiki-content
    if not content:
        content_match = re.search(
            r'<div[^>]*class="[^"]*wiki-content[^"]*"[^>]*>(.*?)</div\s*>',
            html,
            re.DOTALL
        )
        if content_match:
            content = content_match.group(1)

    # Fallback: get a large chunk from middle of document
    if not content or len(content) < 200:
        # Find where title ends
        title_pos = html.find(title) if title != "Unknown" else 0
        content = html[title_pos + 200 : title_pos + 5000]

    if not content:
        return title, ""

    # Clean up HTML tags while preserving structure
    content = re.sub(r'</p>', '\n', content, flags=re.IGNORECASE)
    content = re.sub(r'</div>', '\n', content, flags=re.IGNORECASE)
    content = re.sub(r'</li>', '\n', content, flags=re.IGNORECASE)
    content = re.sub(r'</tr>', '\n', content, flags=re.IGNORECASE)
    content = re.sub(r'</td>', ' | ', content, flags=re.IGNORECASE)
    content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
    content = re.sub(r'<h[1-6][^>]*>([^<]*)</h[1-6]>', r'\n\n### \1\n', content, flags=re.IGNORECASE)
    content = re.sub(r'<strong[^>]*>([^<]*)</strong>', r'\1', content, flags=re.IGNORECASE)
    content = re.sub(r'<em[^>]*>([^<]*)</em>', r'\1', content, flags=re.IGNORECASE)
    content = re.sub(r'<[^>]+>', '', content)
    content = unescape(content)

    # Clean up whitespace
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    return title, '\n'.join(lines)


def scrape_pages():
    """Scrape all pages and save to file."""
    client = httpx.Client(timeout=15)
    output = Path("data/raw_goszakup_wiki.txt")

    print(f"Scraping goszakup.gov.kz wiki to {output}")
    print("=" * 70)

    with open(output, 'w', encoding='utf-8') as f:
        successful = 0
        failed = 0

        for page_id, description in PAGE_IDS:
            url = f"https://wiki.goszakup.gov.kz/pages/viewpage.action?pageId={page_id}"

            try:
                print(f"[{page_id:10d}] {description:40s} ... ", end='', flush=True)

                response = client.get(url, timeout=15)
                response.raise_for_status()

                title, content = extract_page_content(response.text)

                if len(content) > 100:
                    f.write(f"=== PAGE: {title} ===\n")
                    f.write(content)
                    f.write("\n=== END ===\n\n")
                    print(f"OK ({len(content)} chars)")
                    successful += 1
                else:
                    print("Empty content")
                    failed += 1

            except Exception as e:
                print(f"Error: {str(e)[:40]}")
                failed += 1

    print("=" * 70)
    print(f"Successful: {successful}, Failed: {failed}")
    print(f"File size: {output.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    scrape_pages()
