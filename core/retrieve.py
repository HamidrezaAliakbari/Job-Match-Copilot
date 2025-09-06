"""Simple retrieval utilities using TF–IDF and cosine similarity.

This module provides a helper to find the most similar lines in a resume to a given query string.
In a more powerful system you would use embeddings and a vector database, but TF–IDF
works well enough for small demos and does not require network access or extra dependencies.
"""

from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def retrieve_evidence(lines: List[str], query: str, top_k: int = 3) -> List[str]:
    """Return up to `top_k` lines from `lines` most relevant to `query`.

    Args:
        lines: List of strings (resume sentences).
        query: The requirement or question.
        top_k: Number of evidence lines to return.

    Returns:
        A list of strings, the best matching lines sorted by similarity descending.
    """
    if not lines or not query:
        return []
    # Fit a TF–IDF vectoriser on the resume lines plus the query
    docs = lines + [query]
    vectoriser = TfidfVectorizer().fit(docs)
    vectors = vectoriser.transform(docs)
    # Compute cosine similarity between the query vector and all resume lines
    similarities = cosine_similarity(vectors[-1], vectors[:-1]).flatten()
    # Sort indexes by similarity descending
    top_indices = similarities.argsort()[::-1][:top_k]
    # Filter out zero similarity results
    evidence = [lines[i] for i in top_indices if similarities[i] > 0]
    return evidence