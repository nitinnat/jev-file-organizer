import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .models import FileEvidence

TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9'-]{2,}")
NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,63}")
STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "been", "before", "being",
    "between", "but", "can", "could", "document", "file", "for", "from", "had",
    "has", "have", "into", "its", "more", "not", "of", "only", "other", "our",
    "page", "should", "some", "such", "than", "that", "the", "their", "then",
    "there", "these", "they", "this", "through", "to", "under", "very", "was",
    "view", "were", "which", "will", "with", "would", "your", "aarch64", "arm64",
    "updated",
}
GENERAL_CATEGORIES = {
    "Finance": {"bank", "billing", "expense", "financial", "invoice", "payment", "revenue"},
    "Receipts": {"amount", "merchant", "paid", "purchase", "receipt", "subtotal", "total"},
    "Taxes": {"deduction", "irs", "tax", "taxable", "w2", "withholding"},
    "Work": {"business", "client", "meeting", "milestone", "project", "quarterly"},
    "Reports": {"analysis", "dashboard", "metric", "report", "results", "summary"},
    "Legal": {"agreement", "contract", "legal", "party", "signature", "terms"},
    "Medical": {"clinic", "health", "lab", "medical", "patient", "prescription"},
    "Travel": {"booking", "departure", "flight", "hotel", "itinerary", "travel"},
    "Education": {"assignment", "course", "education", "lecture", "school", "student"},
    "Gaming": {"game", "league", "player", "pokemon", "rank"},
    "Housing": {"apartment", "lease", "property", "rent", "resident", "tenant"},
    "Insurance": {"coverage", "insured", "insurance", "policy", "premium"},
}
FILETYPE_CATEGORIES = {
    "Archives": {".7z", ".rar", ".tar.gz", ".tgz", ".zip"},
    "Software Installers": {".deb", ".dmg", ".exe", ".msi", ".pkg", ".rpm"},
    "Web Pages": {".htm", ".html"},
}
NAME_ALIASES = {
    "invoice": "Invoices",
    "policy": "Policies",
    "receipt": "Receipts",
    "report": "Reports",
    "screenshot": "Screenshots",
}


@dataclass(frozen=True)
class WordStat:
    word: str
    count: int
    documents: int


@dataclass(frozen=True)
class DiscoveryCorpus:
    words: tuple[WordStat, ...]
    candidate_names: tuple[str, ...]
    candidate_reasons: tuple[str, ...] = ()


def build_corpus(
    evidence: list[FileEvidence],
    existing_folders: tuple[Path, ...],
    configured_names: tuple[str, ...] = (),
    max_words: int = 50,
    max_candidates: int = 16,
) -> DiscoveryCorpus:
    counts: Counter[str] = Counter()
    document_counts: Counter[str] = Counter()
    filename_phrases: Counter[str] = Counter()
    extensions: Counter[str] = Counter()

    for item in evidence:
        words = normalize_words(item.content)
        counts.update(words)
        document_counts.update(set(words))
        name_words = normalize_words(item.path.stem.replace("_", " ").replace("-", " "))
        filename_phrases.update(
            set(name_words)
            | {
                " ".join(pair)
                for pair in zip(name_words, name_words[1:], strict=False)
            }
        )
        name = item.path.name.casefold()
        extensions.update(
            [".tar.gz" if name.endswith(".tar.gz") else item.path.suffix.casefold()]
        )

    stats = tuple(
        WordStat(word, count, document_counts[word])
        for word, count in counts.most_common(max_words)
    )
    existing = {path.name.casefold() for path in existing_folders}
    candidates: list[str] = []
    reasons: list[str] = []

    for name in configured_names:
        add_candidate(candidates, reasons, name, "configured in .jfo.toml", existing)

    repeated_phrases = sorted(
        (item for item in filename_phrases.items() if item[1] >= 2),
        key=lambda item: (-item[1], -len(item[0].split()), item[0]),
    )
    for phrase, count in repeated_phrases:
        add_candidate(
            candidates,
            reasons,
            NAME_ALIASES.get(phrase, phrase.title()),
            f"repeated in {count} filenames",
            existing,
        )

    for name, suffixes in FILETYPE_CATEGORIES.items():
        matches = [(suffix, extensions[suffix]) for suffix in suffixes if extensions[suffix]]
        if sum(count for _, count in matches) >= 2:
            detail = ", ".join(f"{count} {suffix}" for suffix, count in sorted(matches))
            add_candidate(candidates, reasons, name, detail, existing)

    for name, keywords in GENERAL_CATEGORIES.items():
        matches = [
            (word, document_counts[word])
            for word in keywords
            if document_counts[word] >= 2
        ]
        if matches:
            word, documents = max(matches, key=lambda match: match[1])
            add_candidate(
                candidates,
                reasons,
                name,
                f"corpus term '{word}' appears in {documents} files",
                existing,
            )

    return DiscoveryCorpus(
        words=stats,
        candidate_names=tuple(candidates[:max_candidates]),
        candidate_reasons=tuple(reasons[:max_candidates]),
    )


def normalize_words(text: str) -> list[str]:
    return [
        word
        for match in TOKEN_PATTERN.finditer(text)
        if (word := match.group(0).casefold()) not in STOP_WORDS
    ]


def add_candidate(
    candidates: list[str],
    reasons: list[str],
    name: str,
    reason: str,
    existing: set[str],
) -> None:
    cleaned = " ".join(name.split()).strip(" -_")
    if (
        not NAME_PATTERN.fullmatch(cleaned)
        or cleaned.casefold() in existing
        or cleaned.casefold() in {candidate.casefold() for candidate in candidates}
    ):
        return
    candidates.append(cleaned)
    reasons.append(reason)
