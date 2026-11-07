"""Build the FAISS index from data/schemes.json.

Run once (and again whenever schemes.json changes):
    python -m scripts.build_index
Needs an embedding provider (GOOGLE_API_KEY or OPENAI_API_KEY in .env).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_community.vectorstores import FAISS  # noqa: E402
from langchain_core.documents import Document  # noqa: E402

import config  # noqa: E402
from knowledge_base import load_schemes, scheme_text  # noqa: E402
from llm import get_embeddings  # noqa: E402


def main() -> None:
    emb = get_embeddings()
    if emb is None:
        sys.exit("No embedding provider configured. Set GOOGLE_API_KEY or OPENAI_API_KEY in .env.")
    docs = [
        Document(
            page_content=scheme_text(s),
            metadata={"scheme_id": s.scheme_id, "level": s.level, "state": s.state, "category": s.category},
        )
        for s in load_schemes().values()
    ]
    index = FAISS.from_documents(docs, emb)
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    index.save_local(str(config.INDEX_DIR))
    print(f"Indexed {len(docs)} schemes into {config.INDEX_DIR}")


if __name__ == "__main__":
    main()
