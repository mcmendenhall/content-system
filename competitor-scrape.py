# Competitor Scraper - Build Topical Maps by Scraping Competitor Websites
# ============================================================================
# This script crawls competitor websites in a human-like manner to extract topical hierarchy.
# It captures navigation structure, titles, headings, and text for later processing.
#
# Usage:
#     python competitor_scraper.py --max_pages 100 --max_workers 5 --max_depth 2
#
# Arguments:
#     --max_pages    (optional) Maximum number of pages to crawl per site (default 100)
#     --max_workers  (optional) Number of competitor sites to scrape in parallel (default 5)
#     --max_depth    (optional) How many link levels deep to crawl (default 1)
#
# Output:
#     - competitor-scrape/topical-maps/<domain>.json
#     - competitor-scrape/raw_pages/<domain>/*.html and *.json
#     - competitor-scrape/competitor_dashboard.html (overview)
#
# Dependencies:
#     pip install requests beautifulsoup4 tqdm lxml
# ============================================================================

import os
import time
import random
import json
import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

# --- Config ---
OUTPUT_DIR = "competitor-scrape"
TOPICAL_MAPS_DIR = os.path.join(OUTPUT_DIR, "topical-maps")
RAW_PAGES_DIR = os.path.join(OUTPUT_DIR, "raw_pages")
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0",
]

# --- Utility Functions ---

def random_delay(domain):
    delay = random.uniform(1.5, 5.0)
    print(f"[{domain}] Sleeping {delay:.2f} seconds...")
    time.sleep(delay)

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
    }

def safe_filename(url):
    return url.strip("/").replace("/", "_").replace(":", "").replace("?", "").replace("&", "").replace("=", "")

def save_page(domain, url, html, parsed_info):
    domain_dir = os.path.join(RAW_PAGES_DIR, domain)
    os.makedirs(domain_dir, exist_ok=True)

    filename_base = safe_filename(url.replace(f"https://{domain}", "").replace(f"http://{domain}", "") or "home")
    html_path = os.path.join(domain_dir, f"{filename_base}.html")
    json_path = os.path.join(domain_dir, f"{filename_base}.json")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(parsed_info, f, indent=2)

def extract_info(html):
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string.strip() if soup.title else "")
    h1 = (soup.h1.get_text(strip=True) if soup.h1 else "")
    h2s = [h2.get_text(strip=True) for h2 in soup.find_all('h2')][:5]
    text_snippet = soup.get_text(separator=' ', strip=True)[:500]

    return {
        "title": title,
        "h1": h1,
        "h2s": h2s,
        "text_snippet": text_snippet
    }

def is_valid_link(link, domain):
    if not link.startswith("http"):
        return False
    if domain not in link:
        return False
    if any(x in link for x in ["#", "/wp-login", "/cart", "/checkout", "/account"]):
        return False
    return True

def get_nav_links(html, base_url, domain):
    soup = BeautifulSoup(html, "lxml")
    links = set()
    navs = soup.find_all(["nav", "header", "footer"])
    for nav in navs:
        for a in nav.find_all('a', href=True):
            full_url = urljoin(base_url, a['href'])
            if is_valid_link(full_url, domain):
                links.add(full_url)
    return list(links)

def clean_url(url):
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"

# --- Core Scraping Function ---

def crawl_site(base_url, max_pages, max_depth):
    parsed = urlparse(base_url)
    domain = parsed.netloc.replace("www.", "")
    print(f"\n[{domain}] 🌐 Starting crawl (Max depth: {max_depth})")

    visited = set()
    to_visit = [(base_url, 0)]  # (url, current_depth)
    topical_map = {}

    pbar = tqdm(total=max_pages, desc=f"[{domain}] Crawling")

    while to_visit and len(visited) < max_pages:
        url, depth = to_visit.pop(0)
        if url in visited:
            continue

        try:
            print(f"[{domain}] Visiting (Depth {depth}): {url}")
            response = requests.get(url, headers=get_random_headers(), timeout=10)
            if response.status_code != 200:
                print(f"[{domain}] Failed to fetch {url} (Status {response.status_code})")
                continue

            html = response.text
            page_info = extract_info(html)
            save_page(domain, url, html, page_info)

            topical_map[page_info['h1'] or page_info['title'] or url] = []

            # Only add more links if depth < max_depth
            if depth < max_depth:
                nav_links = get_nav_links(html, base_url, domain)
                print(f"[{domain}] Found {len(nav_links)} links at depth {depth}")
                for link in nav_links:
                    if link not in visited and link not in [u for u, _ in to_visit]:
                        to_visit.append((link, depth + 1))

            visited.add(url)
            random_delay(domain)
            pbar.update(1)

        except Exception as e:
            print(f"[{domain}] Error visiting {url}: {e}")
            continue

    pbar.close()

    # Save topical map
    os.makedirs(TOPICAL_MAPS_DIR, exist_ok=True)
    map_path = os.path.join(TOPICAL_MAPS_DIR, f"{domain}.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(topical_map, f, indent=2)

    print(f"\n[{domain}] ✅ Finished: {len(visited)} pages scraped.\n")

    return {"domain": domain, "pages_scraped": len(visited)}

# --- Dashboard HTML Creator ---

def build_dashboard(scrape_results):
    dashboard_path = os.path.join(OUTPUT_DIR, "competitor_dashboard.html")
    html = "<html><head><title>Competitor Dashboard</title></head><body>"
    html += "<h1>Competitor Scrape Dashboard</h1><table border='1' cellpadding='5' cellspacing='0'>"
    html += "<tr><th>Domain</th><th>Pages Scraped</th><th>Topical Map</th><th>Raw Pages</th></tr>"

    for result in scrape_results:
        domain = result['domain']
        pages = result['pages_scraped']
        map_link = f"topical-maps/{domain}.json"
        raw_link = f"raw_pages/{domain}/"
        html += f"<tr><td>{domain}</td><td>{pages}</td><td><a href='{map_link}'>{domain}.json</a></td><td><a href='{raw_link}'>Folder</a></td></tr>"

    html += "</table></body></html>"

    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Dashboard generated: {dashboard_path}")

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_pages", type=int, default=100, help="Max pages per site to crawl")
    parser.add_argument("--max_workers", type=int, default=5, help="Number of sites to scrape in parallel")
    parser.add_argument("--max_depth", type=int, default=1, help="Maximum crawl depth (default 1)")
    args = parser.parse_args()

    competitor_sites = []

    print("Paste competitor domains or URLs (one per line), then type 'DONE' and Enter:")
    while True:
        line = input()
        if line.strip().lower() == "done":
            break
        cleaned = clean_url(line.strip())
        if cleaned not in competitor_sites:
            competitor_sites.append(cleaned)

    if not competitor_sites:
        print("No competitor domains entered. Exiting.")
        return

    print(f"\nStarting scraping {len(competitor_sites)} competitors with {args.max_workers} workers... (Max depth {args.max_depth})")

    scrape_results = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [executor.submit(crawl_site, site, args.max_pages, args.max_depth) for site in competitor_sites]
        for f in futures:
            result = f.result()
            scrape_results.append(result)

    build_dashboard(scrape_results)

if __name__ == "__main__":
    main()
