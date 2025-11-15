import openai
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Get API key and topic from .env
openai.api_key = os.getenv("OPENAI_API_KEY")
topic = os.getenv("ARTICLE_TOPIC")

# Build the corrected prompt
prompt = f"""
You are an expert SEO and technical content strategist.

Generate a highly detailed article outline for the topic: "{topic}".

Rules:
- Every bullet point should represent one complete sentence or micro-topic that would be covered in the article.
- Structure the outline in logical macro headings (H2s), with supporting bullets (one per sentence).
- Cover the following:
  • Mention your main entity and sub-entities naturally in the first 1–2 paragraphs.
  • Clear first sentences (e.g. answer the main question immediately).
  • Each heading addresses differnt contextual layers (e.g. definition, process, cost, compliance, timeline - depends on topic).
  • Include information gain (e.g. provide facts and angles not easily found elsewhere).
  • Internal semantic connections (e.g. reuse meaning-related words naturally).
  • Implicit question coverage (e.g. even if search volume is low).
  • Micro-semantics under macro headings (e.g. small details under broad ideas).
  • Word2Vec proximity awareness (e.g. use conceptually related words).
  • Embedded FAQ section (e.g. explicit and inferred questions).
  • Entity mentions (e.g. proper names like SOC 2, HIPAA, vCISO must appear naturally).
  • Schema markup suggestion (e.g. FAQPage, Article, mentions).
  * Minimize obvious / Unnecessary Definitions unless its a really introductory article

Output Format:
H2: [Section Title]
- Bullet (sentence-level detail)
- Bullet
- Bullet

Repeat for every major section.

Every relevant aspect of the topic must be covered fully with no gaps.
Think like Google's NLP systems when structuring the content.
"""

# Call OpenAI ChatCompletion endpoint (GPT-4 Turbo)
response = openai.ChatCompletion.create(
    model="gpt-4-1106-preview",
    messages=[
        {"role": "system", "content": "You are a technical SEO and semantic content expert."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.2,
    max_tokens=4096
)

# Print the generated outline
print(response["choices"][0]["message"]["content"])