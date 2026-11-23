"""Chargement, découpage et recherche dans les documents de l'entreprise.

Recherche lexicale BM25 implémentée sans dépendance lourde : simple à
expliquer, rapide, et suffisante pour une base documentaire de PME.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Mots vides français : ignorés dans la recherche.
STOPWORDS = set(
    """a au aux avec ce ces cet cette dans de des du elle en et est il ils je la le les leur
    leurs lui ma mais me mes mon ne nos notre nous on ou où par pas pour qu que qui sa se ses
    son sont sur ta te tes ton tu un une vos votre vous y d l j n s c qu' est-ce comment quel
    quelle quels quelles quoi combien faut dois doit peut peux être avoir fait faire si""".split()
)


@dataclass
class Chunk:
    """Un passage de document, avec sa source pour les citations."""
    source: str
    section: str
    text: str
    tokens: list[str] = field(default_factory=list, repr=False)


def normalize(text: str) -> str:
    """Minuscules et suppression des accents (« congés » -> « conges »)."""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", normalize(text))
    # Racinisation minimale : retire le pluriel en -s / -x.
    out = []
    for w in words:
        if w in STOPWORDS or len(w) < 2:
            continue
        if len(w) > 3 and w[-1] in "sx":
            w = w[:-1]
        out.append(w)
    return out


def read_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8")


def chunk_text(text: str, source: str, max_words: int = 180) -> list[Chunk]:
    """Découpe par titres Markdown, puis par blocs de max_words mots."""
    chunks: list[Chunk] = []
    section = source
    buffer: list[str] = []

    def flush():
        words = " ".join(buffer).split()
        for i in range(0, len(words), max_words):
            part = " ".join(words[i:i + max_words]).strip()
            if part:
                chunks.append(Chunk(source, section, part))
        buffer.clear()

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            section = line.lstrip("#").strip() or source
        elif line.strip():
            buffer.append(line.strip())
    flush()
    for c in chunks:
        c.tokens = tokenize(f"{c.section} {c.text}")
    return chunks


class BM25Index:
    """Index BM25 (Okapi) sur une liste de passages."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.avgdl = sum(len(c.tokens) for c in chunks) / max(len(chunks), 1)
        df: Counter = Counter()
        for c in chunks:
            df.update(set(c.tokens))
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(c.tokens) for c in chunks]

    def search(self, query: str, k: int = 4, min_score: float = 0.5) -> list[tuple[Chunk, float]]:
        terms = tokenize(query)
        scored = []
        for chunk, tf in zip(self.chunks, self.tf):
            dl = len(chunk.tokens)
            score = 0.0
            for t in terms:
                if t in tf:
                    f = tf[t]
                    score += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if score >= min_score:
                scored.append((chunk, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


def build_index(paths: list[Path]) -> BM25Index:
    chunks: list[Chunk] = []
    for p in paths:
        chunks.extend(chunk_text(read_document(p), p.name))
    return BM25Index(chunks)
