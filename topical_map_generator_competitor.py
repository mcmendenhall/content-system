# --- Import Dependencies ---
import os
import json
import openai
import numpy as np
from collections import Counter
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv
import asyncio
import argparse

# --- Load Environment Variables ---
load_dotenv()

# --- Configuration ---
SCRAPED_DIR = "scraped-articles"
OUTPUT_DIR = "semantic"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
NUM_TOP_ENTITIES = 50
NUM_TOP_KEYWORDS = 30
ENTITY_GROUPING_THRESHOLD = 0.7

# --- Initialize OpenAI Client (🔥 Updated) ---
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Helper Functions ---

def load_scraped_articles(file_path):
    """Load scraped articles from JSON."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    articles = data.get("articles", [])
    print(f"✅ Loaded {len(articles)} articles from {file_path}")
    return articles

async def extract_entities_openai(text):
    """Extract named entities using OpenAI."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Extract a flat list of important named entities (people, places, organizations, products, concepts) from the text. Return ONLY a list."},
                {"role": "user", "content": text[:4000]}
            ],
            temperature=0,
            max_tokens=500
        )
        # 🔥 Updated parsing
        extracted = response.choices[0].message.content
        entities = [e.strip("- ").strip() for e in extracted.splitlines() if e.strip()]
        return entities
    except Exception as e:
        print(f"❌ OpenAI entity extraction error: {e}")
        return []

def extract_keywords_keybert(texts):
    """Extract keywords from all articles using KeyBERT."""
    model = SentenceTransformer(EMBEDDING_MODEL)
    kw_model = KeyBERT(model)
    all_keywords = []
    for text in texts:
        keywords = kw_model.extract_keywords(text, keyphrase_ngram_range=(1,3), stop_words='english', top_n=10)
        all_keywords.extend([kw for kw, _ in keywords])
    print(f"✅ Extracted {len(all_keywords)} total keywords")
    return list(set(all_keywords))

def group_entities(entities):
    """Group similar entities together using cosine similarity."""
    model = SentenceTransformer(EMBEDDING_MODEL)
    embeddings = model.encode(entities, convert_to_tensor=True)
    similarity_matrix = util.cos_sim(embeddings, embeddings)

    groups = []
    used = set()

    for idx, entity in enumerate(entities):
        if idx in used:
            continue
        group = [entity]
        used.add(idx)
        for jdx, sim_score in enumerate(similarity_matrix[idx]):
            if jdx in used:
                continue
            if sim_score > ENTITY_GROUPING_THRESHOLD:
                group.append(entities[jdx])
                used.add(jdx)
        groups.append(group)

    print(f"✅ Grouped {len(entities)} entities into {len(groups)} clusters")
    return groups

def save_topical_map(topic, grouped_entities, keywords, output_dir=OUTPUT_DIR):
    """Save the topical map into a JSON file."""
    os.makedirs(output_dir, exist_ok=True)

    topical_map = {
        "main_topic": topic,
        "subtopics": [],
        "related_keywords": keywords
    }

    for group in grouped_entities:
        topical_map["subtopics"].append({
            "topic": group[0],
            "related_entities": group
        })

    safe_topic = topic.strip().lower().replace(" ", "_")
    output_path = os.path.join(output_dir, f"{safe_topic}_topical_map.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(topical_map, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved topical map to {output_path}")

# --- Main Processing Function ---

async def generate_topical_map(keyword):
    """Main function to generate the topical map."""
    safe_keyword = keyword.strip().lower().replace(" ", "_")
    file_path = os.path.join(SCRAPED_DIR, f"{safe_keyword}.json")

    if not os.path.exists(file_path):
        print(f"❌ Scraped file not found: {file_path}")
        return

    print(f"🔍 Starting Topical Map Generation for: {keyword}")

    # --- Load scraped articles ---
    articles = load_scraped_articles(file_path)
    texts = [section.get("content", "") for article in articles for section in article.get("sections", [])]

    if not texts:
        print(f"❌ No valid article content found in {file_path}")
        return

    # --- Entity Extraction via OpenAI ---
    print("🧠 Extracting entities using OpenAI GPT-4...")
    all_entities = []
    for text in texts:
        entities = await extract_entities_openai(text)
        all_entities.extend(entities)
    top_entities = [e for e, _ in Counter(all_entities).most_common(NUM_TOP_ENTITIES)]
    print(f"✅ Found {len(top_entities)} top entities")

    # --- Keyword Extraction via KeyBERT ---
    print("🧠 Extracting keywords with KeyBERT...")
    keywords = extract_keywords_keybert(texts)
    keywords = keywords[:NUM_TOP_KEYWORDS]
    print(f"✅ Selected {len(keywords)} top keywords")

    # --- Group Entities into Subtopics ---
    print("🧠 Grouping entities into subtopics...")
    grouped_entities = group_entities(top_entities)

    # --- Save Topical Map ---
    print("💾 Saving topical map...")
    save_topical_map(keyword, grouped_entities, keywords)

    print("\n🎉 Topical Map Generation Completed Successfully!")

# --- CLI Interface ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Topical Map from Scraped Articles")
    parser.add_argument("keyword", type=str, help="Main keyword for the topical map")
    args = parser.parse_args()

    asyncio.run(generate_topical_map(args.keyword))
