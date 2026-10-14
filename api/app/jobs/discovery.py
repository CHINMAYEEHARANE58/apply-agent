"""Normalization and conservative cross-source duplicate detection."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.jobs.discovery_schemas import NormalizedJob

_TOKEN_RE = re.compile(r"[^\W_]+(?:[+#.][^\W_]*)*", re.UNICODE)
_STOP_WORDS = frozenset({"a", "an", "and", "for", "in", "intern", "internship", "of", "the", "to", "with"})


def normalized_text(value: str | None) -> str:
    return " ".join(token.strip(".") for token in _TOKEN_RE.findall((value or "").casefold()) if token.strip("."))


def description_terms(description: str) -> frozenset[str]:
    return frozenset(term for term in normalized_text(description).split() if len(term) > 2 and term not in _STOP_WORDS)


def description_similarity(left: str, right: str) -> float:
    left_terms = description_terms(left)
    right_terms = description_terms(right)
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def job_fingerprint(job: NormalizedJob) -> str:
    """Stable fingerprint for exact-ish duplicates.

    The description term set makes word order and insignificant casing changes
    stable, while the ingestion service additionally applies a conservative
    similarity threshold for near-duplicates from different sources.
    """

    parts = (
        normalized_text(job.company),
        normalized_text(job.title),
        normalized_text(job.location),
        " ".join(sorted(description_terms(job.description))),
    )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def are_reasonable_duplicates(left: NormalizedJob, right: NormalizedJob) -> bool:
    if job_fingerprint(left) == job_fingerprint(right):
        return True
    if normalized_text(left.company) != normalized_text(right.company):
        return False
    if normalized_text(left.title) != normalized_text(right.title):
        return False
    if normalized_text(left.location) != normalized_text(right.location):
        return False
    return description_similarity(left.description, right.description) >= 0.82


@dataclass(frozen=True)
class DeduplicatedJob:
    canonical_job: NormalizedJob
    source_urls: tuple[str, ...]


class JobDeduplicator:
    """In-memory policy component used before persistence.

    A database repository must persist every URL from ``source_urls``. This
    component never makes a network request and never treats descriptions as
    executable instructions.
    """

    def __init__(self) -> None:
        self._items: list[DeduplicatedJob] = []

    def add(self, job: NormalizedJob) -> tuple[DeduplicatedJob, bool]:
        for index, item in enumerate(self._items):
            if are_reasonable_duplicates(item.canonical_job, job):
                urls = tuple(dict.fromkeys([*item.source_urls, str(job.url)]))
                merged = DeduplicatedJob(item.canonical_job, urls)
                self._items[index] = merged
                return merged, True
        item = DeduplicatedJob(job, (str(job.url),))
        self._items.append(item)
        return item, False

    def extend(self, jobs: Iterable[NormalizedJob]) -> tuple[DeduplicatedJob, ...]:
        for job in jobs:
            self.add(job)
        return tuple(self._items)
