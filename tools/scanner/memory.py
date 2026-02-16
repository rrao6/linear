#!/usr/bin/env python3
"""
Vector memory using ChromaDB for semantic search and historical context.
Stores classified intel, competitor profiles, and trends for retrieval.

Usage:
    python3 tools/scanner/memory.py --store classified.json    # Index intel
    python3 tools/scanner/memory.py --search "Roku sports"     # Search
    python3 tools/scanner/memory.py --duplicates classified.json  # Find dupes
    python3 tools/scanner/memory.py --context "pluto_tv"       # Build context
"""

import argparse
import json
import os
import ssl
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = ROOT / "data" / "chroma"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def get_embeddings(texts, model="text-embedding-3-small"):
    """Get embeddings from OpenAI."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("No OPENAI_API_KEY in environment")

    body = json.dumps({
        "model": model,
        "input": texts,
    }).encode()

    req = Request(
        "https://api.openai.com/v1/embeddings",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with urlopen(req, timeout=30, context=ctx) as resp:
        result = json.loads(resp.read())
        return [item["embedding"] for item in result["data"]]


class VectorMemory:
    """ChromaDB-backed vector memory for competitive intel."""

    def __init__(self, persist_dir=None):
        import chromadb

        persist_dir = persist_dir or str(CHROMA_DIR)
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=persist_dir)

        # Collections
        self.intel_collection = self.client.get_or_create_collection(
            name="intel",
            metadata={"description": "Classified competitive intel items"},
        )
        self.profiles_collection = self.client.get_or_create_collection(
            name="profiles",
            metadata={"description": "Competitor profiles"},
        )
        self.trends_collection = self.client.get_or_create_collection(
            name="trends",
            metadata={"description": "Market trends"},
        )

    def store_intel(self, intel_items):
        """Index classified intel items."""
        if not intel_items:
            return 0

        texts = []
        ids = []
        metadatas = []

        for item in intel_items:
            if isinstance(item, dict):
                d = item
            else:
                d = item.to_dict()

            doc_id = d.get("article_hash", "")
            if not doc_id:
                continue

            text = f"{d.get('title', '')}. {d.get('summary', '')}"
            texts.append(text)
            ids.append(doc_id)
            metadatas.append({
                "competitor_id": d.get("competitor_id", ""),
                "category": d.get("category", ""),
                "relevance_score": d.get("relevance_score", 0),
                "impact_score": d.get("impact_score", 0),
                "published_at": d.get("published_at", ""),
                "url": d.get("url", ""),
                "indexed_at": datetime.now().isoformat(),
            })

        if not texts:
            return 0

        # Get embeddings
        embeddings = get_embeddings(texts)

        # Upsert to ChromaDB
        self.intel_collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        return len(texts)

    def store_profiles(self, profiles):
        """Index competitor profiles."""
        if not profiles:
            return 0

        texts = []
        ids = []
        metadatas = []

        for p in profiles:
            cid = p.get("competitor_id", "")
            if not cid:
                continue

            text = (
                f"{p.get('name', cid)}: "
                f"Strategy: {p.get('strategy_focus', '')}. "
                f"Recent moves: {', '.join(p.get('recent_moves', []))}. "
                f"Strengths: {', '.join(p.get('strengths_observed', []))}."
            )
            texts.append(text)
            ids.append(f"profile_{cid}_{datetime.now().strftime('%Y%m%d')}")
            metadatas.append({
                "competitor_id": cid,
                "threat_level": p.get("threat_level", 0),
                "indexed_at": datetime.now().isoformat(),
            })

        if not texts:
            return 0

        embeddings = get_embeddings(texts)
        self.profiles_collection.upsert(
            ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas
        )
        return len(texts)

    def store_trends(self, trends):
        """Index market trends."""
        if not trends:
            return 0

        texts = []
        ids = []
        metadatas = []

        for t in trends:
            name = t.get("name", "")
            if not name:
                continue

            text = (
                f"Trend: {name}. {t.get('description', '')}. "
                f"Direction: {t.get('direction', '')}. "
                f"Prediction: {t.get('prediction', '')}."
            )
            texts.append(text)
            ids.append(f"trend_{name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}")
            metadatas.append({
                "category": t.get("category", ""),
                "direction": t.get("direction", ""),
                "strength": t.get("strength", 0),
                "indexed_at": datetime.now().isoformat(),
            })

        if not texts:
            return 0

        embeddings = get_embeddings(texts)
        self.trends_collection.upsert(
            ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas
        )
        return len(texts)

    def search(self, query, collection_name="intel", n_results=10, where=None):
        """Semantic search across a collection."""
        collection = {
            "intel": self.intel_collection,
            "profiles": self.profiles_collection,
            "trends": self.trends_collection,
        }.get(collection_name, self.intel_collection)

        embedding = get_embeddings([query])[0]

        kwargs = {
            "query_embeddings": [embedding],
            "n_results": min(n_results, collection.count() or 1),
        }
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)

        items = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                items.append({
                    "id": doc_id,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })

        return items

    def find_duplicates(self, intel_items, threshold=0.85):
        """Find near-duplicate intel items already in memory."""
        if not intel_items or self.intel_collection.count() == 0:
            return []

        duplicates = []
        for item in intel_items:
            if isinstance(item, dict):
                text = f"{item.get('title', '')}. {item.get('summary', '')}"
                item_hash = item.get("article_hash", "")
            else:
                text = f"{item.title}. {item.summary}"
                item_hash = item.article_hash

            results = self.search(text, "intel", n_results=3)
            for r in results:
                # distance < (1 - threshold) means very similar
                # ChromaDB returns L2 distance; lower = more similar
                if r["distance"] < (1 - threshold) * 2 and r["id"] != item_hash:
                    duplicates.append({
                        "new_hash": item_hash,
                        "existing_id": r["id"],
                        "distance": r["distance"],
                        "existing_doc": r["document"][:100],
                    })

        return duplicates

    def build_context(self, competitor_id=None, query=None, max_items=20):
        """Build historical context for analysis agents."""
        context = {"intel": [], "profiles": [], "trends": []}

        if competitor_id:
            # Get recent intel for this competitor
            where = {"competitor_id": competitor_id}
            query_text = query or f"{competitor_id} recent news and updates"
            context["intel"] = self.search(query_text, "intel", max_items, where)
            context["profiles"] = self.search(
                f"{competitor_id} profile", "profiles", 3, where
            )
        elif query:
            context["intel"] = self.search(query, "intel", max_items)

        # Always get recent trends
        context["trends"] = self.search(
            query or "FAST streaming market trends", "trends", 5
        )

        return context

    def stats(self):
        """Get collection statistics."""
        return {
            "intel_count": self.intel_collection.count(),
            "profiles_count": self.profiles_collection.count(),
            "trends_count": self.trends_collection.count(),
        }


def main():
    parser = argparse.ArgumentParser(description="Vector memory for competitive intel")
    parser.add_argument("--store", help="JSON file to index")
    parser.add_argument("--search", help="Search query")
    parser.add_argument("--collection", default="intel",
                       choices=["intel", "profiles", "trends"])
    parser.add_argument("--context", help="Build context for competitor ID")
    parser.add_argument("--duplicates", help="Check for duplicates in JSON file")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    parser.add_argument("--n", type=int, default=10, help="Number of results")
    args = parser.parse_args()

    mem = VectorMemory()

    if args.stats:
        print(json.dumps(mem.stats(), indent=2))
        return

    if args.store:
        with open(args.store) as f:
            data = json.load(f)

        # Store intel
        intel = data.get("intel", [])
        if intel:
            count = mem.store_intel(intel)
            print(f"Stored {count} intel items")

        # Store profiles
        profiles = data.get("profiles", {}).get("profiles", [])
        if profiles:
            count = mem.store_profiles(profiles)
            print(f"Stored {count} profiles")

        # Store trends
        trends = data.get("trends", {}).get("trends", [])
        if trends:
            count = mem.store_trends(trends)
            print(f"Stored {count} trends")

        print(f"\nMemory stats: {json.dumps(mem.stats(), indent=2)}")

    elif args.search:
        results = mem.search(args.search, args.collection, args.n)
        for r in results:
            print(f"\n[{r['id']}] (distance: {r['distance']:.4f})")
            print(f"  {r['document'][:200]}")
            if r["metadata"]:
                print(f"  metadata: {json.dumps(r['metadata'], indent=4)}")

    elif args.context:
        ctx = mem.build_context(args.context)
        print(json.dumps(ctx, indent=2))

    elif args.duplicates:
        with open(args.duplicates) as f:
            data = json.load(f)
        intel = data.get("intel", [])
        dupes = mem.find_duplicates(intel)
        print(f"Found {len(dupes)} potential duplicates")
        for d in dupes:
            print(f"  {d['new_hash']} ~ {d['existing_id']} (dist: {d['distance']:.4f})")


if __name__ == "__main__":
    main()
