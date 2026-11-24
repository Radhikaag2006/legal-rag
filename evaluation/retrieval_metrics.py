"""
Computes Hit@5, Hit@10, MRR and average latency for:
  1. Vector retrieval only
  2. Vector retrieval + reranker

Run from project root:  python evaluation/retrieval_metrics.py
"""
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from retriever.retriever import Retriever
from reranker.reranker import Reranker

# Number of candidates fetched from the vector DB before reranking.
# Must be >= 10 (larger lets the reranker promote lower-ranked chunks).
CANDIDATE_POOL = 30


def dedupe_by_document(chunks):
    """Keep only the best-ranked chunk per judgment (document-level ranking)."""
    seen, unique = set(), []
    for chunk in chunks:
        doc_id = str(chunk["document_id"])
        if doc_id not in seen:
            seen.add(doc_id)
            unique.append(chunk)
    return unique


def first_relevant_rank(chunks, relevant):
    """1-based document rank of the first relevant judgment, or None."""
    for rank, chunk in enumerate(dedupe_by_document(chunks)[:10], start=1):
        if str(chunk["document_id"]) in relevant:
            return rank
    return None


def summarize(name, ranks, latencies):
    n = len(ranks)
    hit5 = sum(1 for r in ranks if r is not None and r <= 5) / n
    hit10 = sum(1 for r in ranks if r is not None and r <= 10) / n
    mrr = sum(1 / r for r in ranks if r is not None) / n
    avg_lat = sum(latencies) / n
    return name, hit5, hit10, mrr, avg_lat


def main():
    with open(PROJECT_ROOT / "evaluation" / "questions.json", encoding="utf-8") as f:
        questions = [q for q in json.load(f) if q["relevant_doc_ids"]]

    retriever = Retriever()
    reranker = Reranker()

    # Warm-up so model load time isn't counted in latency
    retriever.retrieve("warm up", top_k=CANDIDATE_POOL)

    vec_ranks, vec_lat = [], []
    rer_ranks, rer_lat = [], []

    for q in questions:
        relevant = {str(d) for d in q["relevant_doc_ids"]}

        # --- Vector only ---
        t0 = time.perf_counter()
        vec = retriever.retrieve(q["question"], top_k=CANDIDATE_POOL)
        vec_lat.append(time.perf_counter() - t0)
        vec_ranks.append(first_relevant_rank(vec, relevant))

        # --- Vector + reranker ---
        t0 = time.perf_counter()
        cand = retriever.retrieve(q["question"], top_k=CANDIDATE_POOL)
        reranked = reranker.rerank(q["question"], cand)
        rer_lat.append(time.perf_counter() - t0)
        rer_ranks.append(first_relevant_rank(reranked, relevant))

        print(f"Q{q['id']}: vector rank={vec_ranks[-1]}  reranked rank={rer_ranks[-1]}")

    rows = [
        summarize("Vector Retrieval Only", vec_ranks, vec_lat),
        summarize("Vector Retrieval + Reranker", rer_ranks, rer_lat),
    ]

    print(f"\nQuestions evaluated: {len(questions)}\n")
    print(f"{'Configuration':<30}{'Hit@5':>8}{'Hit@10':>8}{'MRR':>8}{'Latency(s)':>12}")
    for name, h5, h10, mrr, lat in rows:
        print(f"{name:<30}{h5:>8.3f}{h10:>8.3f}{mrr:>8.3f}{lat:>12.3f}")


if __name__ == "__main__":
    main()
