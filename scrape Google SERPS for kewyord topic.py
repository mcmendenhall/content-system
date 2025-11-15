import os
import json
import argparse
import requests
from newspaper import Article
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
DATAFORSEO_API_KEY = os.getenv("DATAFORSEO_API_KEY")

# STEP 1: Get full SERP result from DataForSEO
def get_serp_data(query, api_key, depth=10):
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json"
    }

    payload = [{
        "keyword": query,
        "location_code": 2840,
        "language_code": "en",
        "device": "desktop",
        "os": "windows",
        "depth": depth
    }]

    resp = requests.post(
        "https://api.dataforseo.com/v3/serp/google/organic/live/advanced",
        json=payload,
        headers=headers
    )

    data = resp.json()
    try:
        result = data["tasks"][0]["result"][0]
        return result
    except Exception as e:
        print("❌ Failed to parse SERP results:", json.dumps(data, indent=2))
        return {}

# STEP 2: Extract article content
def extract_article_data(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return {
            "url": url,
            "title": article.title,
            "clean_text": article.text,
            "raw_html": article.html
        }
    except Exception as e:
        return {"url": url, "error": str(e)}

# STEP 3: Extract H2/H3 headings
def extract_headings(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        return [h.get_text(strip=True) for h in soup.find_all(['h2', 'h3'])]
    except Exception as e:
        return []

# STEP 4: Split text by headings
def split_text_by_headings(text, headings):
    sections = []
    lower_text = text.lower()
    last_index = 0

    for heading in headings:
        h_lower = heading.lower()
        index = lower_text.find(h_lower)
        if index != -1 and index > last_index:
            content = text[last_index:index].strip()
            if sections and content:
                sections[-1]['content'] = content
            sections.append({"heading": heading, "content": ""})
            last_index = index + len(h_lower)

    if sections:
        remainder = text[last_index:].strip()
        if remainder:
            sections[-1]['content'] = remainder
    else:
        sections = [{"heading": "Body", "content": text.strip()}]

    return sections

# STEP 5: Build SERP feature block
def extract_serp_features(result):
    features = {
        "featured_snippet": None,
        "people_also_ask": [],
        "related_searches": [],
        "knowledge_panel": None
    }

    for item in result.get("items", []):
        t = item.get("type")

        if t == "featured_snippet":
            features["featured_snippet"] = {
                "title": item.get("title"),
                "featured_title": item.get("featured_title"),
                "description": item.get("description"),
                "url": item.get("url")
            }
            if item.get("table"):
                features["featured_snippet"]["table"] = {
                    "header": item["table"].get("table_header"),
                    "rows": item["table"].get("table_content")
                }

        elif t == "people_also_ask":
            for paa in item.get("items", []):
                answer = None
                source_url = None
                expanded = paa.get("expanded_element", [])
                if expanded:
                    answer = expanded[0].get("description")
                    source_url = expanded[0].get("url")

                features["people_also_ask"].append({
                    "question": paa.get("title"),
                    "answer": answer,
                    "source_url": source_url
                })

        elif t == "related_searches":
            for term in item.get("items", []):
                features["related_searches"].append({
                    "term": term,
                    "url": f"https://www.google.com/search?q={term.replace(' ', '+')}"
                })

        elif t == "knowledge_graph":
            features["knowledge_panel"] = {
                "title": item.get("title"),
                "subtitle": item.get("subtitle"),
                "description": item.get("description"),
                "source_url": item.get("url"),
                "image": item.get("image_url"),
                "attributes": [
                    {"key": a.get("key"), "value": a.get("value")}
                    for a in item.get("attributes", [])
                ]
            }

    return {k: v for k, v in features.items() if v}


# MAIN
def run_scraper(query, num_results=1):
    if not DATAFORSEO_API_KEY:
        raise ValueError("Missing DATAFORSEO_API_KEY in .env")

    print(f"🔍 Searching: {query}")
    result_data = get_serp_data(query, DATAFORSEO_API_KEY, depth=num_results)
    if not result_data:
        return

    urls = [item["url"] for item in result_data.get("items", []) if "url" in item]
    features = extract_serp_features(result_data)
    results = []

    # Setup output directories
    safe_keyword = query.strip().lower().replace(" ", "_")
    output_dir = "scraped-articles"
    html_dir = os.path.join(output_dir, safe_keyword)
    os.makedirs(html_dir, exist_ok=True)

    for i, url in enumerate(urls, 1):
        print(f"→ [{i}/{len(urls)}] {url}")
        article = extract_article_data(url)
        if "error" in article:
            results.append(article)
            continue

        # Save HTML
        html_filename = f"article{i}.html"
        html_path = os.path.join(html_dir, html_filename)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(article.get("raw_html", ""))

        headings = extract_headings(url)
        sections = split_text_by_headings(article["clean_text"], headings)

        results.append({
            "url": url,
            "title": article.get("title", "Untitled"),
            "sections": sections,
            "raw_html_path": html_path.replace("\\", "/"),
            "raw_html": article.get("raw_html", "")
        })

    # Save final JSON
    export_data = {
        "keyword": query,
        "serp_features": features,
        "articles": results
    }

    json_path = os.path.join(output_dir, f"{safe_keyword}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Exported JSON to {json_path}")
    print(f"🗂️  HTML files saved in: {html_dir}")

# CLI
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape articles and SERP features using DataForSEO")
    parser.add_argument("keyword", type=str, help="Keyword to search")
    parser.add_argument("--num", type=int, default=10, help="Number of results to fetch")
    args = parser.parse_args()

    run_scraper(args.keyword, num_results=args.num)
